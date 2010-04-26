"""
Collector for F5 BigIp Local Traffic Manager

 - MIB: F5-BIGIP-LOCAL-MIB.txt
 - Supported hardware:
    - any F5 BigIp LTM

A tuple (virtual server, pool) is mapped to a virtual server (we only
consider the default pool). Pool members are mapped to real servers.
"""

import socket
import re

from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.python import log
from zope.interface import implements

from qcss3.collector.icollector import ICollector, ICollectorFactory
from qcss3.collector.datastore import LoadBalancer, VirtualServer, RealServer, SorryServer
from qcss3.collector.loadbalancer.generic import GenericCollector, str2oid, oid2str

class F5LTMCollector(GenericCollector):
    """
    Collect data for F5 BigIP LTM content switchs.
    """
    implements(ICollector)

    oids = {
        # Nodes
        'ltmNodeAddrScreenName': '.1.3.6.1.4.1.3375.2.2.4.1.2.1.12',
        # Pools
        'ltmPoolLbMode': '.1.3.6.1.4.1.3375.2.2.5.1.2.1.2',
        'ltmPoolStatusAvailState': '.1.3.6.1.4.1.3375.2.2.5.5.2.1.2',
        'ltmPoolStatusEnabledState': '.1.3.6.1.4.1.3375.2.2.5.5.2.1.3',
        'ltmPoolStatusDetailReason': '.1.3.6.1.4.1.3375.2.2.5.5.2.1.5',
        'ltmPoolMemberMonitorRule': '.1.3.6.1.4.1.3375.2.2.5.3.2.1.14',
        'ltmPoolMemberRatio': '.1.3.6.1.4.1.3375.2.2.5.3.2.1.6',
        'ltmPoolMemberWeight': '.1.3.6.1.4.1.3375.2.2.5.3.2.1.7',
        'ltmPoolMemberPriority': '.1.3.6.1.4.1.3375.2.2.5.3.2.1.8',
        'ltmPoolMemberDynamicRatio': '.1.3.6.1.4.1.3375.2.2.5.3.2.1.9',
        'ltmPoolMbrStatusAvailState': '.1.3.6.1.4.1.3375.2.2.5.6.2.1.5',
        'ltmPoolMbrStatusEnabledState': '.1.3.6.1.4.1.3375.2.2.5.6.2.1.6',
        'ltmPoolMbrStatusDetailReason': '.1.3.6.1.4.1.3375.2.2.5.6.2.1.8',
        # Virtual servers
        'ltmVirtualServAddrType': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.2',
        'ltmVirtualServAddr': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.3',
        'ltmVirtualServPort': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.6',
        'ltmVirtualServEnabled': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.9',
        'ltmVirtualServTranslateAddr': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.13',
        'ltmVirtualServDefaultPool': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.19',
        'ltmVirtualServProfileType': '.1.3.6.1.4.1.3375.2.2.10.5.2.1.3',
        'ltmVsStatusAvailState': '.1.3.6.1.4.1.3375.2.2.10.13.2.1.2',
        'ltmVsStatusEnabledState': '.1.3.6.1.4.1.3375.2.2.10.13.2.1.3',
        'ltmVsStatusDetailReason': '.1.3.6.1.4.1.3375.2.2.10.13.2.1.5',
        }

    kind = "F5 LTM"
    modes = {
		0: 'round robin',
		1: 'ratio member',
		2: 'least conn member',
		3: 'observed member',
		4: 'predictive member',
		5: 'ratio node',
		6: 'least conn node',
		7: 'fastest node',
		8: 'observed node',
		9: 'predictive node',
		10: 'dynamic ratio',
		11: 'fastest response',
		12: 'least sessions',
		13: 'dynamic ratio member',
		14: 'l3 address',
        }
    availstates = {
		0: 'down',
		1: 'up',
		2: 'down',
		3: 'down',
		4: 'down',
		5: 'down',
        }
    enabledstates = {
        0: 'disabled',
        1: 'enabled',
        2: 'disabled',
        3: 'disabled',
        }

    def parse(self, vs=None, rs=None):
        """
        Parse vs and rs into vs, r, p
        """
        if vs is not None:
            if rs is not None:
                mo = re.match(r"([\d\.]+):(\d+)", rs)
                if not mo:
                    raise ValueError("%r is not a valid real server" % rs)
                r, p = mo.group(1), int(mo.group(2))
                try:
                    socket.inet_aton(r)
                except:
                    raise ValueError("%r is not a valid IP:port" % rs)
                return vs, r, p
            return vs, None, None
        return None, None, None

    def collect(self, vs=None, rs=None):
        """
        Collect data for an F5 Big IP LTM.

        @param vs: any string identifying a virtual server
        @param rs: IP:port identifying a pool member
        """
        vs, r, p = self.parse(vs, rs)
        if vs is not None:
            if r is not None:
                # Collect data to refresh a specific real server
                d = self.process_rs(vs, r, p)
            else:
                # Collect data to refresh a virtual server
                d = self.process_vs(vs)
        else:
            # Otherwise, collect everything
            d = self.process_all()
        return d

    @defer.deferredGenerator
    def process_all(self):
        """
        Process data when no virtual server and no real server are provided.
        """
        # Retrieve all data
        for oid in self.oids:
            w = defer.waitForDeferred(self.proxy.walk(self.oids[oid]))
            yield w
            w.getResult()

        # For each virtual server, build it
        for v in self.cache('ltmVirtualServAddrType'):
            v = oid2str(v)
            vs = defer.waitForDeferred(self.process_vs(v))
            yield vs
            vs = vs.getResult()
            if vs is not None:
                self.lb.virtualservers["%s" % v] = vs
        yield self.lb
        return

    @defer.deferredGenerator
    def process_vs(self, v):
        """
        Process data for a given virtual server when no real server is provided

        @param v: virtual server
        @return: a maybe deferred C{IVirtualServer}
        """
        ov = str2oid(v)
        # Retrieve some data if needed
        oids = []
        for o in self.oids:
            if o.startswith("ltmVirtualServ") or o.startswith("ltmVs"):
                if not o.startswith("ltmVirtualServProfile"):
                    oids.append((o, ov))
        oids = tuple(oids)
        c = defer.waitForDeferred(self.cache_or_get(*oids))
        yield c
        c.getResult()

        # No IPv6 virtual server
        if self.cache(('ltmVirtualServAddrType', ov)) != 1:
            log.msg("In %r, unable to handle IPv6 virtual server %d, skip it" % (self.lb.name, v))
            yield None
            return

        # Get pool
        p = self.cache(('ltmVirtualServDefaultPool', ov))
        op = str2oid(p)
        oids = []
        for o in self.oids:
            if o.startswith("ltmPool") and not o.startswith("ltmPoolMbr") and \
                    not o.startswith("ltmPoolMember"):
                oids.append((o, op))
        oids = tuple(oids)
        c = defer.waitForDeferred(self.cache_or_get(*oids))
        yield c
        c.getResult()

        vip = "%s:%d" % (socket.inet_ntoa(self.cache(('ltmVirtualServAddr', ov))),
                         self.cache(('ltmVirtualServPort', ov)))
        protocol = defer.waitForDeferred(self.get_protocol(ov))
        yield protocol
        protocol = protocol.getResult()
        mode = self.modes[self.cache(('ltmPoolLbMode', op))]
        vs = VirtualServer(v, vip, protocol, mode)
        vs.extra["vs availability state"] = \
            self.availstates[self.cache(('ltmVsStatusAvailState', ov))]
        vs.extra["vs enabled state"] = \
            self.enabledstates[self.cache(('ltmVsStatusEnabledState', ov))]
        vs.extra["virtual server detailed reason"] = \
            self.cache(('ltmVsStatusDetailReason', ov))
        vs.extra["address translation"] = \
            self.cache(('ltmVirtualServTranslateAddr', ov)) == 1 and "enabled" or "disabled"
        vs.extra["pool name"] = \
            self.cache(('ltmVirtualServDefaultPool', ov))
        vs.extra["pool availability state"] = \
            self.availstates[self.cache(('ltmPoolStatusAvailState', op))]
        vs.extra["pool enabled state"] = \
            self.enabledstates[self.cache(('ltmPoolStatusEnabledState', op))]
        vs.extra["pool detailed reason"] = \
            self.cache(('ltmPoolStatusDetailReason', op))

        # Find and attach real servers
        if not self.is_cached(('ltmPoolMbrStatusAvailState', op)):
            for o in self.oids:
                if o.startswith('ltmPoolMbr') or o.startswith('ltmPoolMember'):
                    # F5 is buggy here, we need to walk all pool members
                    # pm = defer.waitForDeferred(
                    #    self.proxy.walk("%s.%s.1.4" % (self.oids[o], op)))
                    pm = defer.waitForDeferred(
                        self.proxy.walk(self.oids[o]))
                    yield pm
                    pm.getResult()
        if not self.is_cached(('ltmPoolMbrStatusAvailState', op, 1, 4)):
            log.msg("In %r, unable to handle IPv6 real servers for virtual server %s, skip it" % (self.lb.name, v))
            yield None
            return
        for r in self.cache(('ltmPoolMbrStatusAvailState', op, 1, 4)):
            rip = ".".join(str(a) for a in r[:4])
            port = r[-1]
            rs = defer.waitForDeferred(self.process_rs(v, rip, port))
            yield rs
            rs = rs.getResult()
            if rs is not None:
                vs.realservers["%s:%d" % (rip, port)] = rs

        yield vs
        return

    @defer.deferredGenerator
    def process_rs(self, v, rip, port):
        """
        Process data for a given virtual server and real server.

        @param v: virtual server
        @param rip: real IP
        @param port: port
        """
        # Retrieve some data if needed:
        ov = str2oid(v)
        orip = str2oid(socket.inet_aton(rip))
        p = defer.waitForDeferred(self.cache_or_get(('ltmVirtualServDefaultPool', ov)))
        yield p
        p = p.getResult()
        op = str2oid(p)
        oids = []
        for o in self.oids:
            if o.startswith("ltmPoolMbr") or o.startswith("ltmPoolMember"):
                oids.append((o, op, 1, orip, port))
        oids = tuple(oids)
        c = defer.waitForDeferred(self.cache_or_get(*oids))
        yield c
        c.getResult()

        name = defer.waitForDeferred(self.cache_or_get(('ltmNodeAddrScreenName',
                                                        1, orip)))
        yield name
        name = name.getResult()
        protocol = defer.waitForDeferred(self.get_protocol(ov))
        yield protocol
        protocol = protocol.getResult()
        weight = self.cache(('ltmPoolMemberWeight', op, 1, orip, port))
        avail, enabled = self.cache(('ltmPoolMbrStatusAvailState', op, 1, orip, port),
                                    ('ltmPoolMbrStatusEnabledState', op, 1, orip, port))
        if self.enabledstates[enabled] != "enabled":
            state = "disabled"
        else:
            state = self.availstates[avail]
        rs = RealServer(name, rip, port, protocol, weight, state)
        rs.extra["detailed reason"] = self.cache(('ltmPoolMbrStatusDetailReason',
                                                  op, 1, orip, port))
        rs.extra["monitor rule"] = self.cache(('ltmPoolMemberMonitorRule',
                                               op, 1, orip, port))
        yield rs
        return

    @defer.deferredGenerator
    def get_protocol(self, ov):
        """
        Get protocol for a given virtual server.

        @param ov: virtual server as an OID string
        @return: deferred protocol
        """
        if not self.is_cached(('ltmVirtualServProfileType', ov)):
            # This OID is buggy. It is not possible to walk it
            c = defer.waitForDeferred(self.proxy.walk(self.oids['ltmVirtualServProfileType']))
            yield c
            c.getResult()
        for k in self.cache(('ltmVirtualServProfileType', ov)):
            yield oid2str(k)
            break
        return

    def actions(self, vs=None, rs=None):
        """
        List possible actions.

        On F5, there is no possible action for now.
        """
        return defer.succeed({})


class F5LTMCollectorFactory:
    implements(ICollectorFactory, IPlugin)

    def canBuildCollector(self, proxy, description, oid):
        """
        Does this factory for F5 LTM can build a collector for this agent?

        We only use the OID.
        """
        return oid.startswith('.1.3.6.1.4.1.3375.2.')

    def buildCollector(self, config, proxy, name, description):
        return F5LTMCollector(config, proxy, name, description)

factory = F5LTMCollectorFactory()
