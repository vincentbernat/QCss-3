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
        'ltmPoolMemberSessionStatus': '.1.3.6.1.4.1.3375.2.2.5.3.2.1.13',
        'ltmPoolMemberNewSessionEnable': '.1.3.6.1.4.1.3375.2.2.5.3.2.1.12',
        'ltmPoolMbrStatusAvailState': '.1.3.6.1.4.1.3375.2.2.5.6.2.1.5',
        'ltmPoolMbrStatusEnabledState': '.1.3.6.1.4.1.3375.2.2.5.6.2.1.6',
        'ltmPoolMbrStatusDetailReason': '.1.3.6.1.4.1.3375.2.2.5.6.2.1.8',
        # HTTP class
        'ltmHttpClassPoolName': '.1.3.6.1.4.1.3375.2.2.6.15.1.2.1.4',
        # Virtual servers
        'ltmVirtualServAddrType': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.2',
        'ltmVirtualServAddr': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.3',
        'ltmVirtualServPort': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.6',
        'ltmVirtualServEnabled': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.9',
        'ltmVirtualServTranslateAddr': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.13',
        'ltmVirtualServDefaultPool': '.1.3.6.1.4.1.3375.2.2.10.1.2.1.19',
        'ltmVirtualServProfileType': '.1.3.6.1.4.1.3375.2.2.10.5.2.1.3',
        'ltmVsHttpClassProfileName': '.1.3.6.1.4.1.3375.2.2.10.12.2.1.2',
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
        Parse vs and rs into vs, httpclass, r, p
        """
        if vs is not None:
            httpclass = None
            mo = re.match(r"(.+);(.+)", vs)
            if mo:
                vs = mo.group(1)
                httpclass = mo.group(2)
            if rs is not None:
                mo = re.match(r"([\d\.]+):(\d+)", rs)
                if not mo:
                    raise ValueError("%r is not a valid real server" % rs)
                r, p = mo.group(1), int(mo.group(2))
                try:
                    socket.inet_aton(r)
                except:
                    raise ValueError("%r is not a valid IP:port" % rs)
                return vs, httpclass, r, p
            return vs, httpclass, None, None
        return None, None, None, None

    def collect(self, vs=None, rs=None):
        """
        Collect data for an F5 Big IP LTM.

        @param vs: any string identifying a virtual server
        @param rs: IP:port identifying a pool member
        """
        vs, httpclass, r, p = self.parse(vs, rs)
        if vs is not None:
            if r is not None:
                # Collect data to refresh a specific real server
                d = self.process_rs(vs, httpclass, r, p)
            else:
                # Collect data to refresh a virtual server
                d = self.process_vs(vs, httpclass)
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
        for ov in self.cache('ltmVirtualServAddrType'):
            # Grab HTTP class
            try:
                classes = self.cache(('ltmVsHttpClassProfileName', ".".join([str(x) for x in ov]))).values()
            except KeyError:
                classes = []
            for httpclass in classes + [None]:
                v = oid2str(ov)
                vs = defer.waitForDeferred(self.process_vs(v, httpclass))
                yield vs
                vs = vs.getResult()
                if vs is not None:
                    if httpclass is not None:
                        self.lb.virtualservers["%s;%s" % (v, httpclass)] = vs
                    else:
                        self.lb.virtualservers[v] = vs
        yield self.lb
        return

    @defer.deferredGenerator
    def process_vs(self, v, httpclass):
        """
        Process data for a given virtual server when no real server is provided

        @param v: virtual server
        @param httpclass: HTTP class to use (or C{None} for default pool) to select pool
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
            log.msg("In %r, unable to handle IPv6 virtual server %s, skip it" % (self.lb.name, v))
            yield None
            return

        # Get pool
        if httpclass is None:
            p = self.cache(('ltmVirtualServDefaultPool', ov))
            if not p:
                log.msg("In %r, no pool for %s, skip it" % (self.lb.name, v))
                yield None
                return
        else:
            oc = str2oid(httpclass)
            p = defer.waitForDeferred(self.cache_or_get(('ltmHttpClassPoolName', oc)))
            yield p
            p = p.getResult()
            if not p:
                log.msg("In %r, no pool for %s (class %s), skip it" % (self.lb.name, v, httpclass))
                yield None
                return
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
        vs = VirtualServer(httpclass is None and v or ("%s;%s" % (v, httpclass)),
                           vip, protocol, mode)
        if httpclass:
            vs.extra["http class"] = httpclass
        vs.extra["vs availability state"] = \
            self.availstates[self.cache(('ltmVsStatusAvailState', ov))]
        vs.extra["vs enabled state"] = \
            self.enabledstates[self.cache(('ltmVsStatusEnabledState', ov))]
        vs.extra["virtual server detailed reason"] = \
            self.cache(('ltmVsStatusDetailReason', ov))
        vs.extra["address translation"] = \
            self.cache(('ltmVirtualServTranslateAddr', ov)) == 1 and "enabled" or "disabled"
        vs.extra["pool name"] = p
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
            rs = defer.waitForDeferred(self.process_rs(v, httpclass, rip, port))
            yield rs
            rs = rs.getResult()
            if rs is not None:
                vs.realservers["%s:%d" % (rip, port)] = rs

        yield vs
        return

    @defer.deferredGenerator
    def process_rs(self, v, httpclass, rip, port):
        """
        Process data for a given virtual server and real server.

        @param v: virtual server
        @param httpclass: HTTP class (or C{None} for default pool)
        @param rip: real IP
        @param port: port
        """
        # Retrieve some data if needed:
        ov = str2oid(v)
        orip = str2oid(socket.inet_aton(rip))
        if httpclass is None:
            p = defer.waitForDeferred(self.cache_or_get(('ltmVirtualServDefaultPool', ov)))
        else:
            oc = str2oid(httpclass)
            p = defer.waitForDeferred(self.cache_or_get(('ltmHttpClassPoolName', oc)))
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
        avail, enabled, session = self.cache(
            ('ltmPoolMbrStatusAvailState', op, 1, orip, port),
            ('ltmPoolMbrStatusEnabledState', op, 1, orip, port),
            ('ltmPoolMemberSessionStatus', op, 1, orip, port))
        if session != 1 or self.enabledstates[enabled] != "enabled":
            state = "disabled"
        else:
            state = self.availstates[avail]
        rs = RealServer(name, rip, port, protocol, weight, state)
        rs.extra["detailed reason"] = self.cache(('ltmPoolMbrStatusDetailReason',
                                                  op, 1, orip, port))
        rs.extra["monitor rule"] = self.cache(('ltmPoolMemberMonitorRule',
                                               op, 1, orip, port))
        # Actions
        if self.proxy.writable:
            # ltmPoolMemberNewSessionEnable == 1 means user disabled
            if self.cache(('ltmPoolMemberNewSessionEnable', op, 1, orip, port)) != 1:
                rs.actions['disable'] = 'Disable (permanent)'
            else:
                rs.actions['enable'] = 'Enable (permanent)'
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

    @defer.deferredGenerator
    def execute(self, action, actionargs=None, vs=None, rs=None):
        """
        Execute an action.
        """
        if action not in ["enable", "disable", "operenable", "operdisable"]:
            yield None
            return
        v, httpclass, rip, port = self.parse(vs, rs)
        if rip is None:
            yield {}
            return

        # Get pool
        ov = str2oid(v)
        orip = str2oid(socket.inet_aton(rip))
        if httpclass is None:
            p = defer.waitForDeferred(self.cache_or_get(('ltmVirtualServDefaultPool', ov)))
        else:
            oc = str2oid(httpclass)
            p = defer.waitForDeferred(self.cache_or_get(('ltmHttpClassPoolName', oc)))
        yield p
        p = p.getResult()
        op = str2oid(p)

        d = defer.waitForDeferred(
            self.proxy.set((self.oids['ltmPoolMemberNewSessionEnable'],
                            op, 1, orip, port),
                           action.endswith("enable") and 2 or 1))
        yield d
        d.getResult()
        yield True
        return

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
