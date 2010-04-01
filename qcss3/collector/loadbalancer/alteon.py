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

from twisted.plugin import IPlugin
from zope.interface import implements

from qcss3.collector.icollector import ICollector, ICollectorFactory
from qcss3.collector.datastore import LoadBalancer, VirtualServer, RealServer
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
        'slbVirtServicesInfoState': '.1.3.6.1.4.1.1872.2.5.4.3.4.1.6',
        # Sorry servers
        'slbCurCfgGroupBackupGroup': '.1.3.6.1.4.1.1872.2.5.4.1.1.3.3.1.5',
        'slbCurCfgGroupBackupServer': '.1.3.6.1.4.1.1872.2.5.4.1.1.3.3.1.4',
        'slbCurCfgRealServerBackUp': '.1.3.6.1.4.1.1872.2.5.4.1.1.2.2.1.6',
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
        2: "ok",
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


    def process(self, data, vs=None, rs=None):
        """
        Process all gathered data.

        @param data: collected OIDs
        """
        for v in data['slbCurCfgVirtServerIpAddress']:
            v = int(v.split(".")[-1])
            for s in data['slbCurCfgVirtServiceRealGroup']:
                if int(s.split(".")[-2]) != v:
                    continue
                g = int(data['slbCurCfgVirtServiceRealGroup'][s])
                s = int(s.split(".")[-1])
                # (v,s,g) is our tuple for a virtual server, let's build it
                index = "v%ds%dg%d" % (v, s, g)
                name = " ~ ".join([x for x in
                                   [data['slbCurCfgVirtServerVname'][".%d" % v],
                                    data['slbCurCfgVirtServiceHname'][".%d.%d" % (v, s)],
                                    data['slbCurCfgGroupName'][".%d" % g]] if x])
                if not name: name = index
                vip = "%s:%d" % (data['slbCurCfgVirtServerIpAddress'][".%d" % v],
                                 data['slbCurCfgVirtServiceVirtPort'][".%d.%d" % (v,s)])
                protocol = "TCP"
                if data['slbCurCfgVirtServiceUDPBalance'][".%d.%d" % (v,s)] != 3:
                    protocol = "UDP"
                mode = self.modes[data['slbCurCfgGroupMetric'][".%d" % g]]
                vs = VirtualServer(name, vip, protocol, mode)
                vs.extra["virtual server status"] = \
                    self.states[data['slbCurCfgVirtServerState'][".%d" % v]]
                vs.extra["healthcheck"] = self.healthchecks.get(
                    data['slbCurCfgGroupHealthCheckLayer'][".%d" % g],
                    "unknown")
                self.lb.virtualservers[index] = vs
                # Find and attach real servers
                reals = data['slbCurCfgGroupRealServers'][".%d" % g]
                for i in range(len(reals)):
                    if reals[i] == '\x00':
                        continue
                    for r in range(8):
                        if not ord(reals[i]) & (1 << r):
                            continue
                        r = 8-r + i*8
                        # r is the index of our real server
                        rip = data['slbCurCfgRealServerIpAddr']['.%d' % r]
                        name = data['slbCurCfgRealServerName']['.%d' % r] or rip
                        rport = data['slbCurCfgVirtServiceRealPort']['.%d.%d' % (v,s)]
                        # protocol is left unchanged
                        weight = data['slbCurCfgRealServerWeight']['.%d' % r]
                        state = self.status[
                            data['slbVirtServicesInfoState']['.%d.%d.%d' % (v,s,r)]]
                        rs = RealServer(name, rip, rport, protocol, weight, state)
                        rs.extra["ping interval"] = \
                            data['slbCurCfgRealServerPingInterval']['.%d' % r]
                        rs.extra["fail retry"] = \
                            data['slbCurCfgRealServerFailRetry']['.%d' % r]
                        rs.extra["success retry"] = \
                            data['slbCurCfgRealServerSuccRetry']['.%d' % r]
                        vs.realservers["r%d" % r] = rs
        return self.lb

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
