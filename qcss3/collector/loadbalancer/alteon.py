"""
Collector for Nortel Alteon (Radware Alteon) Application Switch.

 - MIB: ALTEON-CHEEATH-LAYER4-MIB
 - Supported hardware:
    - AAS 2xxx series (for example AAS 2208)
    - AAS 3xxx series (for example AAS 3416)

A tuple (virtual server, virtual service, group) is mapped to a
virtual server. Real servers are mapped to real servers.

Alteon features backup servers and backup groups. A backup server can
be attached to a real server or to a group. A backup group can be
attached to a group. This information is flattened.
"""

import re

from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.python import log
from zope.interface import implements

from qcss3.collector.icollector import ICollector, ICollectorFactory
from qcss3.collector.datastore import LoadBalancer, VirtualServer, RealServer, SorryServer
from generic import GenericCollector

class AlteonCollector(GenericCollector):
    """
    Collect data for Alteon content switchs.
    """
    implements(ICollector)

    oids = {
        # Virtual server
        'slbCurCfgVirtServerVname': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.2.1.10',
        'slbCurCfgVirtServerState': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.2.1.4',
        'slbCurCfgVirtServerIpAddress': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.2.1.2',
        # Virtual service
        'slbCurCfgVirtServiceVirtPort': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.5.1.3',
        'slbCurCfgVirtServiceRealGroup': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.5.1.4',
        'slbCurCfgVirtServiceRealPort': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.5.1.5',
        'slbCurCfgVirtServiceHname': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.5.1.7',
        'slbCurCfgVirtServiceUDPBalance': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.5.1.6',
        # Groups
        'slbCurCfgGroupMetric': '.1.3.6.1.4.1.1872.2.5.4.1.1.3.3.1.3',
        'slbCurCfgGroupName':  '.1.3.6.1.4.1.1872.2.5.4.1.1.3.3.1.8',
        'slbCurCfgGroupHealthCheckLayer': '.1.3.6.1.4.1.1872.2.5.4.1.1.3.3.1.7',
        'slbCurCfgGroupRealServers': '.1.3.6.1.4.1.1872.2.5.4.1.1.3.3.1.2',
        # Real server
        'slbCurCfgRealServerIpAddr': '.1.3.6.1.4.1.1872.2.5.4.1.1.2.2.1.2',
        'slbCurCfgRealServerWeight': '.1.3.6.1.4.1.1872.2.5.4.1.1.2.2.1.3',
        'slbCurCfgRealServerPingInterval': '.1.3.6.1.4.1.1872.2.5.4.1.1.2.2.1.7',
        'slbCurCfgRealServerFailRetry': '.1.3.6.1.4.1.1872.2.5.4.1.1.2.2.1.8',
        'slbCurCfgRealServerSuccRetry': '.1.3.6.1.4.1.1872.2.5.4.1.1.2.2.1.9',
        'slbCurCfgRealServerState': '.1.3.6.1.4.1.1872.2.5.4.1.1.2.2.1.10',
        'slbCurCfgRealServerName': '.1.3.6.1.4.1.1872.2.5.4.1.1.2.2.1.12',
        'slbCurCfgGroupRealServerState': '.1.3.6.1.4.1.1872.2.5.4.1.1.3.5.1.3',
        'slbNewCfgGroupRealServerState': '.1.3.6.1.4.1.1872.2.5.4.1.1.3.6.1.3',
        'slbVirtServicesInfoState': '.1.3.6.1.4.1.1872.2.5.4.3.4.1.6',
        'slbRealServerInfoState': '.1.3.6.1.4.1.1872.2.5.4.3.1.1.7',
        # Sorry servers
        'slbCurCfgGroupBackupGroup': '.1.3.6.1.4.1.1872.2.5.4.1.1.3.3.1.5',
        'slbCurCfgGroupBackupServer': '.1.3.6.1.4.1.1872.2.5.4.1.1.3.3.1.4',
        'slbCurCfgRealServerBackUp': '.1.3.6.1.4.1.1872.2.5.4.1.1.2.2.1.6',
        # Oper
        'slbOperGroupRealServerState': '.1.3.6.1.4.1.1872.2.5.4.4.5.1.3',
        # Apply
        'agApplyConfig': '.1.3.6.1.4.1.1872.2.5.1.1.8.2.0',
        'agApplyPending': '.1.3.6.1.4.1.1872.2.5.1.1.8.1.0',
        }

    kind = "AAS"
    modes = {
        1: "round robin",
        2: "least connections",
        3: "min misses",
        4: "hash",
        5: "response",
        6: "bandwidth",
        7: "phash",
        }
    states = {
        2: "enabled",
        3: "disabled",
        }
    status = {
        1: "disabled",
        2: "up",
        3: "down",
        4: "disabled",
        }
    healthchecks = {
        1: "icmp",
        2: "tcp",
        3: "http",
        44: "httphead",
        4: "dns",
        5: "smtp",
        6: "pop3",
        7: "nntp",
        8: "ftp",
        9: "imap",
        10: "radius",
        11: "sslh",
        12: "script1",
        13: "script2",
        14: "script3",
        15: "script4",
        16: "script5",
        17: "script6",
        18: "script7",
        19: "script8",
        20: "script9",
        21: "script10",
        22: "script11",
        23: "script12",
        24: "script13",
        25: "script14",
        26: "script15",
        27: "script16",
        28: "link",
        29: "wsp",
        30: "wtls",
        31: "ldap",
        32: "udpdns",
        33: "arp",
        34: "snmp1",
        35: "snmp2",
        36: "snmp3",
        37: "snmp4",
        38: "snmp5",
        39: "radiusacs",
        40: "tftp",
        41: "wtp",
        42: "rtsp",
        43: "sipping",
        45: "sipoptions",
        46: "wts",
        47: "dhcp",
        48: "radiusaa",
        116: "script17",
        117: "script18",
        118: "script19",
        119: "script20",
        120: "script21",
        121: "script22",
        122: "script23",
        123: "script24",
        124: "script25",
        125: "script26",
        126: "script27",
        127: "script28",
        128: "script29",
        129: "script30",
        130: "script31",
        131: "script32",
        132: "script33",
        133: "script34",
        134: "script35",
        135: "script36",
        136: "script37",
        137: "script38",
        138: "script39",
        139: "script40",
        140: "script41",
        141: "script42",
        142: "script43",
        143: "script44",
        144: "script45",
        145: "script46",
        146: "script47",
        147: "script48",
        148: "script49",
        149: "script50",
        150: "script51",
        151: "script52",
        152: "script53",
        153: "script54",
        154: "script55",
        155: "script56",
        156: "script57",
        157: "script58",
        158: "script59",
        159: "script60",
        160: "script61",
        161: "script62",
        162: "script63",
        163: "script64",
        }

    def parse(self, vs=None, rs=None):
        """
        Parse vs and rs into v, s, g, r.
        """
        if vs is not None:
            mo = re.match(r"v(\d+)s(\d+)g(\d+)", vs)
            if not mo:
                raise ValueError("%r is not a valid virtual server" % vs)
            v, s, g = int(mo.group(1)), int(mo.group(2)), int(mo.group(3))
            if rs is not None:
                mo = re.match(r"[rb](\d+)", rs)
                if not mo:
                    raise ValueError("%r is not a valid real server" % rs)
                r = int(mo.group(1))
                return v, s, g, r
            return v, s, g, None
        return None, None, None, None

    def collect(self, vs=None, rs=None):
        """
        Collect data for an Alteon
        """
        v, s, g, r = self.parse(vs, rs)
        if v is not None:
            if r is not None:
                # Collect data to refresh a specific real server
                d = self.process_rs(v, s, g, r)
            else:
                # Collect data to refresh a virtual server
                d = self.process_vs(v, s, g)
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
        for v in self.cache('slbCurCfgVirtServerIpAddress'):
            for s in self.cache(('slbCurCfgVirtServiceRealGroup', v)):
                g = self.cache(('slbCurCfgVirtServiceRealGroup', v, s))
                vs = defer.waitForDeferred(self.process_vs(v, s, g))
                yield vs
                vs = vs.getResult()
                if vs is not None:
                    self.lb.virtualservers["v%ds%dg%d" % (v, s, g)] = vs
        yield self.lb
        return

    @defer.deferredGenerator
    def process_vs(self, v, s, g):
        """
        Process data for a given virtual server when no real server is provided

        @param v: virtual server
        @param s: service
        @param g: group
        @return: a maybe deferred C{IVirtualServer} or C{None}
        """
        # Retrieve some data if needed
        c = defer.waitForDeferred(self.cache_or_get(
            ('slbCurCfgVirtServerVname', v),
            ('slbCurCfgVirtServiceHname', v, s),
            ('slbCurCfgGroupName', g),
            ('slbCurCfgVirtServerIpAddress', v),
            ('slbCurCfgVirtServiceVirtPort', v, s),
            ('slbCurCfgVirtServiceUDPBalance', v, s),
            ('slbCurCfgVirtServiceRealPort', v, s),
            ('slbCurCfgVirtServiceUDPBalance', v, s),
            ('slbCurCfgGroupMetric', g),
            ('slbCurCfgVirtServerState', v),
            ('slbCurCfgGroupHealthCheckLayer', g),
            ('slbCurCfgGroupBackupServer', g),
            ('slbCurCfgGroupBackupGroup', g),
            ('slbCurCfgGroupRealServers', g)))
        yield c
        c.getResult()

        # (v,s,g) is our tuple for a virtual server, let's build it
        index = "v%ds%dg%d" % (v, s, g)
        if not self.is_cached(('slbCurCfgGroupName', g)):
            log.msg("In %r, %s is in an inexistant group" % (self.lb.name, index))
            yield None
            return
        name = " ~ ".join([x for x in self.cache(
                    ('slbCurCfgVirtServerVname', v),
                    ('slbCurCfgVirtServiceHname', v, s),
                    ('slbCurCfgGroupName', g)) if x])
        if not name: name = index
        vip = "%s:%d" % tuple(self.cache(('slbCurCfgVirtServerIpAddress', v),
                                         ('slbCurCfgVirtServiceVirtPort', v, s)))
        protocol = "TCP"
        if self.cache(('slbCurCfgVirtServiceUDPBalance', v, s)) != 3:
            protocol = "UDP"
        mode = self.modes[self.cache(('slbCurCfgGroupMetric', g))]
        vs = VirtualServer(name, vip, protocol, mode)
        vs.extra["virtual server status"] = \
            self.states[self.cache(('slbCurCfgVirtServerState', v))]
        vs.extra["healthcheck"] = self.healthchecks.get(
            self.cache(('slbCurCfgGroupHealthCheckLayer', g)),
            "unknown")

        # Find and attach real servers
        reals = self.cache(('slbCurCfgGroupRealServers', g))
        for r in self.bitmap(reals):
            rs = defer.waitForDeferred(self.process_rs(v, s, g, r))
            yield rs
            rs = rs.getResult()
            if rs is None:
                # This real does not exist
                continue
            vs.realservers["r%d" % r] = rs

            # Maybe a backup server?
            backup = defer.waitForDeferred(self.cache_or_get(('slbCurCfgRealServerBackUp', r)))
            yield backup
            backup = backup.getResult()
            if backup:
                rs = defer.waitForDeferred(self.process_rs(v, s, g, backup, True))
                yield rs
                rs = rs.getResult()
                if rs is not None:
                    vs.realservers["b%d" % backup] = rs

        # Attach backup servers
        backup = self.cache(('slbCurCfgGroupBackupServer', g))
        if backup:
            rs = defer.waitForDeferred(self.process_rs(v, s, g, backup, True))
            yield rs
            rs = rs.getResult()
            if rs is not None:
                vs.realservers["b%d" % backup] = rs
        backup = self.cache(('slbCurCfgGroupBackupGroup', g))
        if backup:
            # We need to retrieve corresponding real servers.
            try:
                g = defer.waitForDeferred(
                    self.cache_or_get(('slbCurCfgGroupRealServers', backup)))
                yield g
                g.getResult()
            except:
                log.msg("In %r, %s has an inexistant backup group %d" % (self.lb.name,
                                                                         index, backup))
                yield vs
                return
            for r in self.bitmap(self.cache(('slbCurCfgGroupRealServers', backup))):
                rs = defer.waitForDeferred(self.process_rs(v, s, g, r, True))
                yield rs
                rs = rs.getResult()
                if rs is not None:
                    vs.realservers["b%d" % r] = rs

        yield vs
        return

    @defer.deferredGenerator
    def process_rs(self, v, s, g, r, backup=False):
        """
        Process data for a given virtual server and real server.

        @param v: virtual server
        @param s: service
        @param g: group
        @param r: real server
        @param backup: is it a backup server?
        @return: a maybe deferred C{IRealServer} or C{None}
        """
        # Retrieve some data if needed:
        c = defer.waitForDeferred(self.cache_or_get(
            ('slbCurCfgRealServerIpAddr', r),
            ('slbCurCfgRealServerName', r),
            ('slbCurCfgVirtServiceRealPort', v, s),
            ('slbCurCfgVirtServiceUDPBalance', v, s),
            ('slbCurCfgRealServerWeight', r),
            ('slbVirtServicesInfoState', v, s, r),
            ('slbRealServerInfoState', r),
            ('slbCurCfgRealServerPingInterval', r),
            ('slbCurCfgRealServerFailRetry', r),
            ('slbCurCfgRealServerSuccRetry', r)))
        yield c
        c.getResult()

        # Build the real server
        rip, name, rport = self.cache(
            ('slbCurCfgRealServerIpAddr', r),
            ('slbCurCfgRealServerName', r),
            ('slbCurCfgVirtServiceRealPort', v, s))
        if rip is None:
            log.msg("In %r, inexistant real server %d for v%ds%dg%d" % (self.lb.name,
                                                                        r, v, s, g))
            yield None
            return
        if not name: name = rip
        protocol = "TCP"
        if self.cache(('slbCurCfgVirtServiceUDPBalance', v, s)) != 3:
            protocol = "UDP"
        if not backup:
            weight = self.cache(('slbCurCfgRealServerWeight', r))
            try:
                state = self.status[self.cache(('slbVirtServicesInfoState', v, s, r))]
            except KeyError:
                state = 'disabled'
            rs = RealServer(name, rip, rport, protocol, weight, state)
        else:
            state = self.status[self.cache(('slbRealServerInfoState', r))]
            rs = SorryServer(name, rip, rport, protocol, state)
        pi, fr, sr = self.cache(
            ('slbCurCfgRealServerPingInterval', r),
            ('slbCurCfgRealServerFailRetry', r),
            ('slbCurCfgRealServerSuccRetry', r))
        rs.extra.update({'ping interval': pi,
                         'fail retry': fr,
                         'success retry': sr})
        yield rs
        return

    @defer.deferredGenerator
    def actions(self, vs=None, rs=None):
        """
        List possible actions.

        Possible actions are enable/disable and operenable/operdisable.
        """
        results = {}
        v, s, g, r = self.parse(vs, rs)
        if r is None:
            yield {}
            return
        d = defer.waitForDeferred(
            self.proxy.get([(self.oids['slbOperGroupRealServerState'], g, r),
                            (self.oids['slbCurCfgGroupRealServerState'], g, r)]))
        yield d
        d.getResult()
        if self.cache(('slbOperGroupRealServerState', g, r)) == 1:
            results["operdisable"] = "Disable (oper)"
        else:
            results["operenable"] = "Enable (oper)"
        if self.cache(('slbCurCfgGroupRealServerState', g, r)) == 1:
            results["disable"] = "Disable"
        else:
            results["enable"] = "Enable"
        yield results
        return

    @defer.deferredGenerator
    def execute(self, action, vs=None, rs=None):
        """
        Execute an action.

        @param action: action to be executed
        """
        v, s, g, r = self.parse(vs, rs)
        if r is None:
            yield None
            return
        d = None
        if action == "operenable" or action == "operdisable":
            d = self.proxy.set((self.oids['slbOperGroupRealServerState'], g, r),
                                action == "operenable" and 1 or 2)
            d = defer.waitForDeferred(d)
            yield d
            d.getResult()
            yield True
            return
        elif action == "enable" or action == "disable":
            d = self.proxy.set((self.oids['slbNewCfgGroupRealServerState'], g, r),
                                action == "enable" and 1 or 2)
            d = defer.waitForDeferred(d)
            yield d
            d.getResult()
            d = defer.waitForDeferred(
                self.proxy.get([self.oids['agApplyPending'],
                                self.oids['agApplyConfig']]))
            yield d
            d.getResult()
            if self.cache(('agApplyPending',)) == 2: # apply needed
                if self.cache(('agApplyConfig',)) == 4: # complete
                    d = self.proxy.set((self.oids['agApplyConfig']), 2) # idle
                    d = defer.waitForDeferred(d)
                    yield d
                    d.getResult()
                d = self.proxy.set((self.oids['agApplyConfig']), 1) # apply
                d = defer.waitForDeferred(d)
                yield d
                d.getResult()
            yield True
            return

class AlteonCollectorFactory:
    implements(ICollectorFactory, IPlugin)

    def canBuildCollector(self, proxy, description, oid):
        """
        Does this factory for Alteon can build a collector for this agent?

        We only use the OID.
        """
        return oid.startswith('.1.3.6.1.4.1.1872.1.13.')

    def buildCollector(self, config, proxy, name, description):
        return AlteonCollector(config, proxy, name, description)

factory = AlteonCollectorFactory()
