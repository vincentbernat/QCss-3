"""
Main service for collector
"""

import time
import socket

from twisted.internet import defer
from twisted.application import internet, service
from twisted.plugin import getPlugins
from twisted.names import client
from twisted.python import log

import qcss3.collector.loadbalancer
from qcss3.collector.proxy import AgentProxy
from qcss3.collector.datastore import LoadBalancer
from qcss3.collector.database import IDatabaseWriter
from qcss3.collector.exception import NoPlugin
from qcss3.collector.icollector import ICollectorFactory

class CollectorService(service.Service):
    """Service to collect data from SNMP"""

    def __init__(self, config, dbpool):
        self.config = config
        self.dbpool = dbpool
        self.setName("SNMP collector")
        self.inprogress = {}
        self.cachedcollectors = {}
        AgentProxy.use_getbulk = self.config.get("bulk", True)

    def get_collector(self, lb, caching=False):
        """
        Get a collector for the given load balancer.

        This method support caching collectors. A cached collector is
        only shared between codes requesting a cached collector.

        @param lb: name of the load balancer
        @param caching: if C{True}, may return a cached collector
        @return: a L{LoadBalancerCollector} (deferred)
        """
        if lb not in self.config.get("lb", {}):
            raise UnknownLoadBalancer, "%s is not not a known loadbalancer" % lb

        # Cache
        clbs = self.cachedcollectors.keys()[:]
        for clb in clbs:
            _, age = self.cachedcollectors[clb]
            if time.time() - age > 10:
                del self.cachedcollectors[clb]
        if caching:
            if lb in self.cachedcollectors:
                lb, _ = self.cachedcollectors[lb]
                # See below for why we do this
                d = defer.Deferred()
                lb.addCallbacks(lambda x: d.callback(x) and x or x,
                                lambda x: d.errback(x) and x or x)
                return d

        # Communities
        community = self.config.get("lb", {})[lb]
        if type(community) is list:
            community, wcommunity = community
        else:
            community, wcommunity = community, None
        # If not an IP, try to solve
        d = defer.succeed(lb)
        try:
            socket.inet_aton(lb)
        except:
            d.addCallback(lambda x, lb: client.getHostByName(lb), lb)
        d.addCallback(lambda ip: LoadBalancerCollector(lb, ip,
                                                       community, wcommunity,
                                                       self.config,
                                                       self.dbpool))

        # Cache handling
        if caching:
            # We don't store the deferred as is because we need to
            # keep its result. We create a new deferred that will be
            # triggered when we get our result.
            dd = defer.Deferred()
            d.addCallbacks(lambda x: dd.callback(x) and x or x,
                           lambda x: dd.errback(x) and x or x)
            self.cachedcollectors[lb] = (dd, time.time())

        return d

    def actions(self, lb, vs=None, rs=None, action=None, actionargs=None):
        """
        Give the list of available actions or execute one.

        @param lb: load balancer on which to execute action
        @param vs: virtual server
        @param rs: real server
        @param action: action to execute or C{None} to get a list
        @param actionargs: additional arguments for an action
        """
        d = self.get_collector(lb)
        d.addCallback(lambda collector: collector.actions(vs, rs, action, actionargs))
        return d

    def refresh(self, lb=None, vs=None, rs=None, caching=False):
        """
        Refresh the specified LB or a subset of it

        @param lb: loadbalancer name
        @param vs: if specified, the index of the virtual server
        @param rs: if specified, the index of the real server
        @param caching: may reuse an existing collector (with its own existing cache!)

        If the name of the loadbalancer is not specified, each load
        balancer is refreshed.
        """
        # If we already have a refresh in progress, return it. If we
        # ask to refresh a real server and the corresponding load
        # balancer is refreshing, we wait for the load balancer
        # refresh.
        if (lb, None, None) in self.inprogress:
            return self.inprogress[lb, None, None]
        if lb is not None and vs is not None:
            if (lb, vs, None) in self.inprogress:
                return self.inprogress[lb, vs, None]
            if rs is not None and (lb, vs, rs) in self.inprogress:
                return self.inprogress[lb, vs, rs]

        # Informative message
        if lb is None:
            log.msg("Start global refresh")
        elif vs is None:
            log.msg("Start refresh of load balancer %r" % lb)
        elif rs is None:
            log.msg("Start refresh of virtual server %r for %r" % (vs, lb))
        else:
            log.msg("Start refresh of real server %r in %r for %r" % (rs, vs, lb))

        if lb is None:
            lbs = self.config.get("lb", {}).keys()
        else:
            lbs = [lb]

        d = defer.succeed(lb)
        for alb in lbs:
            d.addCallback(lambda _, alb: self.get_collector(alb, caching), alb)
            d.addCallback(lambda collector: collector.refresh(vs, rs))
            if lb is None:
                # Don't raise an exception if we are refreshing all load balancers
                d.addErrback(lambda x, lb: log.msg(
                        "Error while exploring %s:\n%s" % (lb, x)), alb)
        if lb is None:
            d.addCallback(lambda x: self.expire())

        # Add our deferred to the list of refresh in progress and
        # remove it when everything is done.
        self.inprogress[lb, vs, rs] = d
        d.addBoth(lambda x: self.inprogress.pop((lb, vs, rs), True) and x)
        return d

    def expire(self):
        """
        Expire old load balancers that were not updated after a long time
        """
        d = self.dbpool.runOperation("""
UPDATE loadbalancer
SET deleted=CURRENT_TIMESTAMP
WHERE CURRENT_TIMESTAMP - interval '%(expire)s days' > updated
AND deleted='infinity'
""",
                                     {'expire': self.config.get("expire", 1)})
        return d

class LoadBalancerCollector:
    """Service to collect data for a given load balancer"""

    def __init__(self, lb, ip, community, wcommunity, config, dbpool):
        """
        Create a new load balancer collector

        @param lb: name of the load balancer
        @param ip: IP of the load balancer
        @param community: RO community for SNMP
        @param wcommunity: RW community for SNMP (C{None} for a read-only collector)
        @param config: collector configuration section
        @param dbpool: dbpool
        """
        self.lb = lb
        self.ip = ip
        self.community = community
        self.wcommunity = wcommunity
        self.config = config
        self.dbpool = dbpool
        self.proxy = None
        self.collector = None
        self.description = None

    def getProxy(self):
        """
        Get a proxy to access the load balancer.

        Also stores description, OID and proxy.

        @return: a proxy
        """
        if self.proxy is not None:
            return defer.succeed(self.proxy)
        proxy = AgentProxy(ip=self.ip,
                           community=self.community,
                           wcommunity=self.wcommunity,
                           version=1)
        d = proxy.get(['.1.3.6.1.2.1.1.1.0', # description
                       '.1.3.6.1.2.1.1.2.0', # OID
                       ])
        d.addCallback(lambda x: self.saveProxy(proxy, x))
        return d

    def saveProxy(self, proxy, results):
        """
        Save proxy into the current object.

        @return: the proxy
        """
        self.proxy = proxy
        self.description = results['.1.3.6.1.2.1.1.1.0']
        self.oid = results['.1.3.6.1.2.1.1.2.0']
        return proxy

    @defer.deferredGenerator
    def findCollector(self):
        """Find the plugin that will handle the load balancer"""
        if self.collector is not None:
            yield self.collector
            return
        plugins = []
        for plugin in getPlugins(ICollectorFactory,
                                 qcss3.collector.loadbalancer):
            d = defer.waitForDeferred(defer.maybeDeferred(
                    plugin.canBuildCollector, self.proxy, self.description, self.oid))
            yield d
            d = d.getResult()
            if d:
                plugins.append(plugin)
        if len(plugins) == 1:
            print "Using %s to collect data from %s" % (str(plugins[0].__class__),
                                                        self.lb)
        elif plugins:
            raise NoPlugin, "Too many plugins available for %s: %s" % (
                [str(plugin.__class__) for plugin in plugins], self.lb)
        else:
            raise NoPlugin, "No plugin available for %s" % self.lb
        self.proxy.version = 2  # Switch to version 2
        self.collector = plugins[0].buildCollector(self.config, self.proxy,
                                                   self.lb, self.description)
        yield self.collector
        return

    def writeData(self, data, vs=None, rs=None):
        if data is not None:
            return self.dbpool.runInteraction(IDatabaseWriter(data).write,
                                              [a for a in [self.lb, vs, rs] if a])

    def refresh(self, vs=None, rs=None):
        """
        Refresh the data from LB

        @param vs: if specified, collect only the specified virtual server
        @param rs: if specified, collect only the specified real server
        """
        d = self.getProxy()
        d.addCallback(lambda x: self.findCollector())
        d.addCallback(lambda x: x.collect(vs, rs))
        d.addCallback(lambda x: self.writeData(x, vs, rs))
        return d


    def actions(self, vs=None, rs=None, action=None, actionargs=None):
        """
        Give the list of actions for LB or execute one

        @param vs: if specified, list only for the specified virtual server
        @param rs: if specified, list only for the specified real server
        @param action: if specified, the action to execute
        @param actionargs: additional arguments for an action

        @return: if action is C{None}, a list of actions. Otherwise,
           C{None} if the action did not exist or the result of the
           action (which cannot be C{None}). This may trigger an exception.
        """

        def execute_and_refresh(collector):
            def refresh(x):
                if x is None:
                    # No refresh is action has failed
                    return x
                d = collector.collect(vs, rs)
                d.addCallback(lambda y: self.writeData(y, vs, rs))
                d.addBoth(lambda _: x)
                return d
            d = collector.execute(action, actionargs, vs, rs)
            # We refresh only if the result is not None (action has
            # been executed) We don't alter the original result. Don't
            # refresh a whole load balancer.
            if vs is not None or rs is not None:
                d.addBoth(lambda x: refresh(x))
            return d

        # No write community, no actions
        if self.wcommunity is None:
            return None

        # Otherwise, get a proxy, find a collector and get things done
        d = self.getProxy()
        d.addCallback(lambda x: self.findCollector())
        if action is None:
            d.addCallback(lambda x: x.actions(vs, rs))
        else:
            d.addCallback(lambda x: execute_and_refresh(x))
        return d
