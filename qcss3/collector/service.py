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
        self.config = config.get('collector', {})
        self.dbpool = dbpool
        self.setName("SNMP collector")
        AgentProxy.use_getbulk = self.config.get("bulk", True)

    def refresh(self, lb=None, vs=None, rs=None):
        """
        Refresh the specified LB or a subset of it

        @param lb: loadbalancer name
        @param vs: if specified, the index of the virtual server
        @param rs: if specified, the index of the real server

        If the name of the loadbalancer is not specified, each load
        balancer is refreshed.
        """
        if lb is None:
            lbs = self.config.get("lb", {}).keys()
        else:
            lbs = [lb]
        d = defer.succeed(lb)
        for alb in lbs:
            if alb not in self.config.get("lb", {}):
                # Happens only when we have only one load balancer
                raise UnknownLoadBalancer, "%s is not not a known loadbalancer" % lb
            # If not an IP, try to solve
            try:
                socket.inet_aton(lb)
            except:
                d.addCallback(lambda x, lb: client.getHostByName(lb), alb)
            d.addCallback(lambda ip, lb: LoadBalancerCollector(lb, ip,
                                                               self.config.get("lb", {})[lb],
                                                               self.config,
                                                               self.dbpool).refresh(vs, rs),
                          alb)
            if lb is None:
                # Don't raise an exception if we are refreshing all load balancers
                d.addErrback(lambda x, lb: log.msg(
                        "Error while exploring %s:\n%s" % (lb, x)), alb)
        return d

class LoadBalancerCollector:
    """Service to collect data for a given load balancer"""

    def __init__(self, lb, ip, community, config, dbpool):
        self.lb = lb
        self.ip = ip
        self.community = community
        self.config = config
        self.dbpool = dbpool
        self.proxy = None
        self.description = None

    def getProxy(self):
        """
        Get a proxy to access the load balancer.

        Also stores description, OID and proxy.

        @return: a proxy
        """
        proxy = AgentProxy(ip=self.ip,
                           community=self.community,
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

    def findCollector(self):
        """Find the plugin that will handle the load balancer"""
        plugins = [ plugin for plugin
                    in getPlugins(ICollectorFactory,
                                  qcss3.collector.loadbalancer)
                    if plugin.canBuildCollector(self.proxy, self.description, self.oid) ]
        if len(plugins) == 1:
            print "Using %s to collect data from %s" % (str(plugins[0].__class__),
                                                        self.lb)
        elif plugins:
            raise NoPlugin, "Too many plugins available for %s: %s" % (
                [str(plugin.__class__) for plugin in plugins], self.lb)
        else:
            raise NoPlugin, "No plugin available for %s" % self.lb
        self.proxy.version = 2  # Switch to version 2
        return plugins[0].buildCollector(self.config, self.proxy,
                                         self.lb, self.description)

    def writeData(self, data, vs=None, rs=None):
        return self.dbpool.runInteraction(IDatabaseWriter(data).write,
                                          [a for a in [self.lb, vs, rs] if a])

    def releaseProxy(self):
        """
        Release the proxy

        @return: C{None}
        """
        del self.proxy
        return None

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
        d.addCallbacks(lambda x: self.releaseProxy(),
                       lambda x: self.releaseProxy() or x)
        return d

