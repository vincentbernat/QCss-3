"""
Collector for Cisco CS (previously Arrowpoint)

 - MIB:
   - APENT-MIB
   - ARROWPOINT-CNTEXT-MIB
   - ARROWPOINT-CNTSVCEXT-MIB
   - ARROWPOINT-SVCEXT-MIB
 - Supported hardware:
    - CS 11000 and others

Cisco has changed the base OID from .1.3.6.1.4.1.2467 to
.1.3.6.1.4.1.9.9.368. We handle this using two collectors and two
factory collectors.

An owner and a content is mapped to a virtual server. A service is
mapped to a real server. We ignore groups.
"""

import re

from twisted.plugin import IPlugin
from twisted.internet import defer
from zope.interface import implements

from qcss3.collector.icollector import ICollector, ICollectorFactory
from qcss3.collector.datastore import LoadBalancer, VirtualServer, RealServer, SorryServer
from qcss3.collector.loadbalancer.generic import GenericCollector, str2oid, oid2str

class ArrowOrCsCollector(GenericCollector):
    """
    Collect data for Arrowpoint or Cisco CS

    This is an abstract class. The attribute C{baseoid} should be set
    to the base OID of APENT-MIB. The attribute C{kind} should be set
    too.
    """
    implements(ICollector)

    baseoid = NotImplementedError
    kind = NotImplementedError

    modes = {
        1: 'roundrobin',
        2: 'aca',
        3: 'destip',
        4: 'srcip',
        5: 'domain',
        6: 'url',
        7: 'leastconn',
        8: 'weightedrr',
        9: 'domainhash',
        10: 'urlhash',
        }
    sticky = {
        1: 'none',
        2: 'ssl',
        3: 'cookieurl',
        4: 'url',
        5: 'cookies',
        6: 'sticky-srcip-dstport',
        7: 'sticky-srcip',
        8: 'arrowpoint-cookie',
        9: 'wap-msisdn',
        }
    protocols = {
        0: 'any',
        6: 'TCP',
        17: 'UDP',
        }
    states = {
        1: 'disabled',
        2: 'down',
        4: 'up',
        5: 'down',
        }
    status = {
        0: False,
        1: True
        }
    contents = {
        1: 'http',
        2: 'ftp-control',
        3: 'realaudio-control',
        4: 'ssl',
        5: 'bypass',
        }
    kals = {
        0: 'none',
        1: 'icmp',
        2: 'http',
        3: 'ftp',
        4: 'tcp',
        5: 'named',
        6: 'script',
        }

    def __init__(self, *args, **kwargs):
        oids = {
            # Content
            'apCntIPAddress': '.1.16.4.1.4',
            'apCntIPProtocol': '.1.16.4.1.5',
            'apCntPort': '.1.16.4.1.6',
            'apCntUrl': '.1.16.4.1.7',
            'apCntSticky': '.1.16.4.1.8',
            'apCntBalance': '.1.16.4.1.9',
            'apCntEnable': '.1.16.4.1.11',
            'apCntPersistence': '.1.16.4.1.15',
            'apCntContentType': '.1.16.4.1.43',
            'apCntPrimarySorryServer': '.1.16.4.1.58',
            'apCntSecondSorryServer': '.1.16.4.1.59',
            # Content/Service association
            'apCntsvcSvcName': '.1.18.2.1.3',
            # Services
            'apSvcIPAddress': '.1.15.2.1.3',
            'apSvcIPProtocol': '.1.15.2.1.4',
            'apSvcPort': '.1.15.2.1.5',
            'apSvcKALType': '.1.15.2.1.6',
            'apSvcKALFrequency': '.1.15.2.1.7',
            'apSvcKALMaxFailure': '.1.15.2.1.8',
            'apSvcKALRetryPeriod': '.1.15.2.1.9',
            'apSvcKALUri': '.1.15.2.1.10',
            'apSvcEnable': '.1.15.2.1.12',
            'apSvcWeight': '.1.15.2.1.16',
            'apSvcState': '.1.15.2.1.17',
            'apSvcKALPort': '.1.15.2.1.31'
            }

        self.oids = {}
        for oid in oids:
            self.oids[oid] = "%s%s" % (self.baseoid, oids[oid])
        GenericCollector.__init__(self, *args, **kwargs)

    def parse(self, vs=None, rs=None):
        """
        Parse vs and rs into owner, content, rs
        """
        if vs is not None:
            mo = re.match(r"(.*)|(.*)", vs)
            if not mo:
                raise ValueError("%r is not a valid virtual server" % vs)
            owner, content = mo.groups()
            return owner, content, rs
        return None, None, None

    def collect(self, vs=None, rs=None):
        """
        Collect data.

        A virtual server is OWNER|CONTENT. A real server is SERVICE.
        """
        owner, content, rs = self.parse(vs, rs)
        if owner is not None:
            if rs is not None:
                # Collect data to refresh a specific real server
                d = self.process_rs(rs)
            else:
                # Collect data to refresh a virtual server
                d = self.process_vs(owner, content)
        else:
            # Otherwise, collect everything
            d = self.process_all()
        return d

    @defer.deferredGenerator
    def process_all(self):
        """
        Process data when no virtual server and no real server are provided.

        @return: a deferred C{ILoadBalancer}
        """
        # Retrieve all data
        for oid in self.oids:
            w = defer.waitForDeferred(self.proxy.walk(self.oids[oid]))
            yield w
            w.getResult()

        # For each virtual server, build it
        for o in self.cache('apCntIPAddress'):
            owner, content = oid2str(o)
            vs = defer.waitForDeferred(self.process_vs(owner, content))
            yield vs
            vs = vs.getResult()
            if vs is not None:
                self.lb.virtualservers["%s|%s" % (owner, content)] = vs
        yield self.lb
        return

    @defer.deferredGenerator
    def process_vs(self, owner, content):
        """
        Process data for a given virtual server when no real server is provided

        @param owner: owner of the content
        @param content: content name
        @return: a deferred C{IVirtualServer} or None
        """
        oowner = str2oid(owner)
        ocontent = str2oid(content)
        # Retrieve some data if needed
        oids = []
        for o in self.oids:
            if o.startswith("apCnt") and not o.startswith("apCntsvc"):
                oids.append((o, oowner, ocontent))
        oids = tuple(oids)
        c = defer.waitForDeferred(self.cache_or_get(*oids))
        yield c
        c.getResult()

        # Let's build our virtual server
        vip = "%s:%d" % tuple(self.cache(('apCntIPAddress', oowner, ocontent),
                                         ('apCntPort', oowner, ocontent)))
        protocol = self.protocols[self.cache(('apCntIPProtocol', oowner, ocontent))]
        mode = self.modes[self.cache(('apCntBalance', oowner, ocontent))]
        vs = VirtualServer(content, vip, protocol, mode)

        # Add some extra information
        vs.extra["URL"] = self.cache(('apCntUrl', oowner, ocontent))
        vs.extra["sticky"] = self.sticky[
            self.cache(('apCntSticky', oowner, ocontent))]
        vs.extra["virtual server status"] = self.status[
            self.cache(('apCntEnable', oowner, ocontent))] and "up" or "down"
        vs.extra["persistence"] = self.status[
            self.cache(('apCntPersistence', oowner, ocontent))] and "enabled" or "disabled"
        vs.extra["content type"] = self.contents[
            self.cache(('apCntContentType', oowner, ocontent))]

        # Find and attach real servers
        if not self.is_cached(('apCntsvcSvcName', oowner, ocontent)):
            services = defer.waitForDeferred(
                self.proxy.walk("%s.%s.%s" % (self.oids['apCntsvcSvcName'],
                                              oowner, ocontent)))
            yield services
            services.getResult()
        for r in self.cache(('apCntsvcSvcName', oowner, ocontent)):
            service = oid2str(r)
            rs = defer.waitForDeferred(self.process_rs(service))
            yield rs
            rs = rs.getResult()
            if rs is not None:
                vs.realservers[service] = rs

        # Add backups
        for backup in ["primary", "second"]:
            service = self.cache(('apCnt%sSorryServer' % backup.capitalize(),
                                  oowner, ocontent))
            if not service: continue
            rs = defer.waitForDeferred(self.process_rs(service, backup))
            yield rs
            rs = rs.getResult()
            if rs is not None:
                vs.realservers[service] = rs

        yield vs
        return

    @defer.deferredGenerator
    def process_rs(self, service, backup=False):
        """
        Process data for a given virtual server and real server.

        @param service: service name
        @param backup: C{False} or a string representing backup position

        @return: a deferred C{IRealServer} or None
        """
        oservice = str2oid(service)
        # Retrieve some data if needed:
        oids = []
        for o in self.oids:
            if o.startswith("apSvc"):
                oids.append((o, oservice))
        oids = tuple(oids)
        c = defer.waitForDeferred(self.cache_or_get(*oids))
        yield c
        c.getResult()

        # Build the real server
        rip = self.cache(('apSvcIPAddress', oservice))
        rport = self.cache(('apSvcPort', oservice))
        protocol = self.protocols[
            self.cache(('apSvcIPProtocol', oservice))]
        state = self.states[
            self.cache(('apSvcState', oservice))]
        if not backup:
            weight = self.cache(('apSvcWeight', oservice))
            rs = RealServer(service, rip, rport, protocol, weight, state)
        else:
            rs = SorryServer(service, rip, rport, protocol, state)
            rs.extra["backup type"] = backup

        rs.extra["KAL type"] = self.kals[
            self.cache(('apSvcKALType', oservice))]


        for key, oid in [
            ('KAL frequency', 'apSvcKALFrequency'),
            ('KAL max failure', 'apSvcKALMaxFailure'),
            ('KAL retry period', 'apSvcKALRetryPeriod'),
            ('KAL URI', 'apSvcKALUri'),
            ('KAL port', 'apSvcKALPort')
            ]:
            try:
                rs.extra[key] = self.cache((oid, oservice))
            except KeyError:
                pass
        yield rs
        return

    def actions(self, vs=None, rs=None):
        """
        List possible actions.

        On this equipment, there is no possible action for now.
        """
        return {}

    def execute(self, action, actionargs=None, vs=None, rs=None):
        """
        Execute an action.

        No action are possible on this equipment
        """
        return None

class ArrowCollector(ArrowOrCsCollector):
    """
    Collect data for Arrowpoint Content Switch or from earlier model
    of Cisco CS using the MIB from arrowpoint.
    """
    baseoid = ".1.3.6.1.4.1.2467"
    kind = "ArrowPoint CSS"

class CsCollector(ArrowOrCsCollector):
    """
    Collect data for later model of Cisco CS.
    """
    baseoid = ".1.3.6.1.4.1.9.9.368"
    kind = "Cisco CS"

class CsCollectorFactory:
    """
    Collector factory for later models of Cisco CS
    """
    implements(ICollectorFactory, IPlugin)

    def canBuildCollector(self, proxy, description, oid):
        return oid.startswith('.1.3.6.1.4.1.9.9.368.')

    def buildCollector(self, config, proxy, name, description):
        return CsCollector(config, proxy, name, description)

factory1 = CsCollectorFactory()

class ArrowCollectorFactory:
    """
    Collector factory for earlier models of Cisco CS and Arrowpoint CSS
    """
    implements(ICollectorFactory, IPlugin)

    def canBuildCollector(self, proxy, description, oid):
        return oid.startswith('.1.3.6.1.4.1.2467.')

    def buildCollector(self, config, proxy, name, description):
        return ArrowCollector(config, proxy, name, description)

factory2 = ArrowCollectorFactory()
