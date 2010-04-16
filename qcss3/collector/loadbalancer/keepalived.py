"""
Collector for Keepalived.

 - MIB: KEEPALIVED-MIB
 - Supported hardware:
    - any host running keepalived with SNMP patch

Keepalived groups are encoded into VIP
"""

import re
import socket

from twisted.plugin import IPlugin
from twisted.internet import defer
from zope.interface import implements

from qcss3.collector.icollector import ICollector, ICollectorFactory
from qcss3.collector.datastore import LoadBalancer, VirtualServer, RealServer, SorryServer
from generic import GenericCollector

class KeepalivedCollector(GenericCollector):
    """
    Collect data for Keepalived
    """
    implements(ICollector)

    oids = {
        # Groups
        'virtualServerGroupName': '.1.3.6.1.4.1.9586.100.5.3.1.1.2',
        'virtualServerGroupMemberType': '.1.3.6.1.4.1.9586.100.5.3.2.1.2',
        'virtualServerGroupMemberFwMark': '.1.3.6.1.4.1.9586.100.5.3.2.1.3',
        'virtualServerGroupMemberAddrType': '.1.3.6.1.4.1.9586.100.5.3.2.1.4',
        'virtualServerGroupMemberAddress': '.1.3.6.1.4.1.9586.100.5.3.2.1.5',
        'virtualServerGroupMemberAddr1': '.1.3.6.1.4.1.9586.100.5.3.2.1.6',
        'virtualServerGroupMemberAddr2': '.1.3.6.1.4.1.9586.100.5.3.2.1.7',
        'virtualServerGroupMemberPort': '.1.3.6.1.4.1.9586.100.5.3.2.1.8',
        # Virtual server
        'virtualServerType': '.1.3.6.1.4.1.9586.100.5.3.3.1.2',
        'virtualServerNameOfGroup': '.1.3.6.1.4.1.9586.100.5.3.3.1.3',
        'virtualServerFwMark': '.1.3.6.1.4.1.9586.100.5.3.3.1.4',
        'virtualServerAddrType': '.1.3.6.1.4.1.9586.100.5.3.3.1.5',
        'virtualServerAddress': '.1.3.6.1.4.1.9586.100.5.3.3.1.6',
        'virtualServerPort': '.1.3.6.1.4.1.9586.100.5.3.3.1.7',
        'virtualServerProtocol': '.1.3.6.1.4.1.9586.100.5.3.3.1.8',
        'virtualServerLoadBalancingAlgo': '.1.3.6.1.4.1.9586.100.5.3.3.1.9',
        'virtualServerLoadBalancingKind': '.1.3.6.1.4.1.9586.100.5.3.3.1.10',
        'virtualServerStatus': '.1.3.6.1.4.1.9586.100.5.3.3.1.11',
        'virtualServerVirtualHost': '.1.3.6.1.4.1.9586.100.5.3.3.1.12',
        'virtualServerPersist': '.1.3.6.1.4.1.9586.100.5.3.3.1.13',
        'virtualServerPersistTimeout': '.1.3.6.1.4.1.9586.100.5.3.3.1.14',
        'virtualServerPersistGranularity': '.1.3.6.1.4.1.9586.100.5.3.3.1.15',
        'virtualServerDelayLoop': '.1.3.6.1.4.1.9586.100.5.3.3.1.16',
        'virtualServerRealServersTotal': '.1.3.6.1.4.1.9586.100.5.3.3.1.20',
        'virtualServerRealServersUp': '.1.3.6.1.4.1.9586.100.5.3.3.1.21',
        'virtualServerQuorum': '.1.3.6.1.4.1.9586.100.5.3.3.1.22',
        'virtualServerQuorumStatus': '.1.3.6.1.4.1.9586.100.5.3.3.1.23',
        'virtualServerQuorumUp': '.1.3.6.1.4.1.9586.100.5.3.3.1.24',
        'virtualServerQuorumDown': '.1.3.6.1.4.1.9586.100.5.3.3.1.25',
        'virtualServerHysteresis': '.1.3.6.1.4.1.9586.100.5.3.3.1.26',
        # Real server
        'realServerType': '.1.3.6.1.4.1.9586.100.5.3.4.1.2',
        'realServerAddrType': '.1.3.6.1.4.1.9586.100.5.3.4.1.3',
        'realServerAddress': '.1.3.6.1.4.1.9586.100.5.3.4.1.4',
        'realServerPort': '.1.3.6.1.4.1.9586.100.5.3.4.1.5',
        'realServerStatus': '.1.3.6.1.4.1.9586.100.5.3.4.1.6',
        'realServerWeight': '.1.3.6.1.4.1.9586.100.5.3.4.1.7',
        'realServerUpperConnectionLimit': '.1.3.6.1.4.1.9586.100.5.3.4.1.8',
        'realServerLowerConnectionLimit': '.1.3.6.1.4.1.9586.100.5.3.4.1.9',
        'realServerActionWhenDown': '.1.3.6.1.4.1.9586.100.5.3.4.1.10',
        'realServerNotifyUp': '.1.3.6.1.4.1.9586.100.5.3.4.1.11',
        'realServerNotifyDown': '.1.3.6.1.4.1.9586.100.5.3.4.1.12',
        'realServerFailedChecks': '.1.3.6.1.4.1.9586.100.5.3.4.1.13',
        }

    kind = "KeepAlived"
    grouptypes = {
        1: "fwmark",
        2: "ip",
        3: "iprange"
        }
    virttypes = {
        1: "fwmark",
        2: "ip",
        3: "group"
        }
    protocols = {
        1: "TCP",
        2: "UDP"
        }
    modes = {
        1: 'rr',
        2: 'wrr',
        3: 'lc',
        4: 'wlc',
        5: 'lblc',
        6: 'lblcr',
        7: 'dh',
        8: 'sh',
        9: 'sed',
        10: 'nq',
        99: 'unknown',
        }
    methods = {
        1: 'nat',
        2: 'dr',
        3: 'tun'
        }
    status = {
        1: True,
        2: False
        }

    def collect(self, vs=None, rs=None):
        """
        Collect data for a Keepalived
        """
        if vs is not None:
            mo = re.match(r"v(\d+)", vs)
            if not mo:
                raise ValueError("%r is not a valid virtual server" % vs)
            v = int(mo.group(1))
            if rs is not None:
                mo = re.match(r"r(\d+)", rs)
                if not mo:
                    raise ValueError("%r is not a valid real server" % rs)
                r = int(mo.group(1))
                # Collect data to refresh a specific real server
                d = self.process_rs(v, r)
            else:
                # Collect data to refresh a virtual server
                d = self.process_vs(v)
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
        for v in self.cache('virtualServerType'):
            vs = defer.waitForDeferred(self.process_vs(v))
            yield vs
            vs = vs.getResult()
            if vs is not None:
                self.lb.virtualservers["v%d" % v] = vs
        yield self.lb
        return

    @defer.deferredGenerator
    def process_vs(self, v):
        """
        Process data for a given virtual server when no real server is provided

        @param v: virtual server
        @return: a deferred C{IVirtualServer} or None
        """
        # Retrieve some data if needed
        oids = []
        for o in self.oids:
            if o.startswith("virtualServer") and not o.startswith("virtualServerGroup"):
                oids.append((o, v))
        oids = tuple(oids)
        c = defer.waitForDeferred(self.cache_or_get(*oids))
        yield c
        c.getResult()

        # Let's build our virtual server, the name and the VIP depends on the type
        virttype = self.virttypes[self.cache(('virtualServerType', v))]
        if virttype == "fwmark":
            # We have a firewall mark.
            name = "fwmark %d" % self.cache(('virtualServerFwMark', v))
            vip = "mark%d:0" % self.cache(('virtualServerFwMark', v))
        elif virttype == "ip":
            # We have an IP address. We only support IPv4.
            if self.cache(('virtualServerAddrType', v)) != 1:
                log.msg("unable to handle IPv6 virtual server %d, skip it" % v)
                yield None
                return
            ip = socket.inet_ntoa(self.cache(('virtualServerAddress', v)))
            name = "IP %s" % ip
            vip = "%s:%d" % (ip, self.cache(('virtualServerPort', v)))
        elif virttype == "group":
            # Name is the name of the group
            name = self.cache(('virtualServerNameOfGroup', v))

            # We need to search for the group name in all groups
            if not self.is_cached(('virtualServerGroupName', 1)):
                groups = defer.waitForDeferred(self.proxy.walk(
                        self.oids['virtualServerGroupName']))
                yield groups
                groups.getResult()
            names = []
            for g in self.cache('virtualServerGroupName'):
                if self.cache(('virtualServerGroupName', g)) == name:
                    # We found our group! Let's retrieve some information on it
                    if not self.is_cached(('virtualServerGroupMemberType', g)):
                        for o in self.oids:
                            if o.startswith('virtualServerGroupMember'):
                                groups = defer.waitForDeferred(self.proxy.walk(
                                        self.oids[o]))
                                yield groups
                                groups.getResult()

                    # The name will depend on group types
                    for m in self.cache(('virtualServerGroupMemberType', g)):
                        grouptype = self.grouptypes[
                            self.cache(('virtualServerGroupMemberType', g, m))]
                        if grouptype == "ip" or grouptype == "range":
                            if self.cache(('virtualServerGroupMemberAddrType', g, m)) != 1:
                                continue # Not IPv4
                        if grouptype == "ip":
                            names.append("%s:%d" % (socket.inet_ntoa(
                                        self.cache(('virtualServerGroupMemberAddress', g, m))),
                                                    self.cache(('virtualServerGroupMemberPort',
                                                                g, m))))
                        elif grouptype == "range":
                            names.append("%s-%s:%d" % (socket.inet_ntoa(
                                        self.cache(('virtualServerGroupMemberAddr1', g, m))),
                                                       socket.inet_ntoa(
                                        self.cache(('virtualServerGroupMemberAddr2', g, m))),
                                                       self.cache(('virtualServerGroupMemberPort',
                                                                   g, m))))
                        elif grouptype == "fwmark":
                            names.append("mark%d:%d" % tuple(
                                    self.cache(('virtualServerGroupMemberFwMark', g, m),
                                               ('virtualServerGroupMemberPort', g, m))))
                        else:
                            # Unknown type, continue
                            continue
                    break
            # We need to build the VIP from names
            if not names:
                log.msg("unable to build a VIP for virtual server group %s, skip it" % name)
                yield None
                return
            vip = " + ".join(names)
        else:
            # Unknown type, don't return a load balancer
            log.msg("unknown type for virtual server %d (%d), skip it" % (v, virttype))
            yield None
            return

        protocol = self.protocols[self.cache(('virtualServerProtocol', v))]
        mode = self.modes[self.cache(('virtualServerLoadBalancingAlgo', v))]
        vs = VirtualServer(name, vip, protocol, mode)

        # Add some extra information
        vs.extra["packet-forwarding method"] = self.methods[
            self.cache(('virtualServerLoadBalancingKind', v))]
        vs.extra["virtual server status"] = self.status[
            self.cache(('virtualServerStatus', v))] and "up" or "down"
        for key, oid in [
            ('virtual host', 'virtualServerVirtualHost'),
            ('persist timeout', 'virtualServerPersistTimeout'),
            ('persist granularity', 'virtualServerPersistGranularity'),
            ('check delay', 'virtualServerDelayLoop'),
            ('quorum', 'virtualServerQuorum'),
            ('quorum up command', 'virtualServerQuorumUp'),
            ('quorum down command', 'virtualServerQuorumDown'),
            ('quorum hysterisis', 'virtualServerHysteresis')
            ]:
            try:
                vs.extra[key] = self.cache((oid, v))
            except KeyError:
                pass
        vs.extra["persistence"] = \
            self.status[self.cache(('virtualServerPersist', v))] and "enabled" or \
            "disabled"
        vs.extra["quorum status"] = \
            self.status[self.cache(('virtualServerQuorumStatus', v))] and "met" or \
            "lost"
        vs.extra["real servers"] = "%d up / %d total" % tuple(self.cache(
                ('virtualServerRealServersUp', v),
                ('virtualServerRealServersTotal', v)))

        # Find and attach real servers
        if not self.is_cached(('realServerType', v, 1)):
            reals = defer.waitForDeferred(
                self.proxy.walk("%s.%d" % (self.oids['realServerType'], v)))
            yield reals
            reals.getResult()
        for r in self.cache(('realServerType', v)):
            rs = defer.waitForDeferred(self.process_rs(v, r))
            yield rs
            rs = rs.getResult()
            if rs is not None:
                vs.realservers["r%d" % r] = rs

        yield vs
        return

    @defer.deferredGenerator
    def process_rs(self, v, r):
        """
        Process data for a given virtual server and real server.

        @param v: virtual server
        @param r: real server

        @return: a deferred C{IRealServer} or None
        """
        # Retrieve some data if needed:
        oids = []
        for o in self.oids:
            if o.startswith("realServer"):
                oids.append((o, v, r))
        oids = tuple(oids)
        c = defer.waitForDeferred(self.cache_or_get(*oids))
        yield c
        c.getResult()

        # Build the real server
        if self.cache(('realServerAddrType', v, r)) != 1:
            log.msg("real server %d for virtual server %v is not IPv4, skip it" % (r, v))
            yield None
            return
        rip = socket.inet_ntoa(self.cache(('realServerAddress', v, r)))
        name = rip
        rport = self.cache(('realServerPort', v, r))
        protocol = defer.waitForDeferred(self.cache_or_get(('virtualServerProtocol', v)))
        yield protocol
        protocol = protocol.getResult()
        protocol = self.protocols[protocol]
        if self.cache(('realServerType', v, r)) == 1:
            # Not a sorry server
            weight = self.cache(('realServerWeight', v, r))
            if weight == 0:
                state = 'disabled'
            else:
                state = self.status[self.cache(('realServerStatus', v, r))] and "up" or "down"
            rs = RealServer(name, rip, rport, protocol, weight, state)
            for key, oid in [
                ('upper connection limit', 'realServerUpperConnectionLimit'),
                ('lower connection limit', 'realServerLowerConnectionLimit'),
                ('notify up command', 'realServerNotifyUp'),
                ('notify down command', 'realServerNotifyDown'),
                ('failed checks', 'realServerFailedChecks')
                ]:
                try:
                    rs.extra[key] = self.cache((oid, v, r))
                except KeyError:
                    pass
            rs.extra["on fail"] = \
                self.cache(('realServerActionWhenDown', v, r)) == 1 and "remove" or \
                "inhibit"
        else:
            # Sorry server, not much information
            rs = SorryServer(name, rip, rport, protocol, "up")
        yield rs
        return

class KeepalivedCollectorFactory:
    implements(ICollectorFactory, IPlugin)

    def canBuildCollector(self, proxy, description, oid):
        """
        Does this factory for Keepalived can build a collector for this agent?

        The OID is of no use here, we check that we have a keepalived agent.
        """
        d = proxy.get('.1.3.6.1.4.1.9586.100.5.1.1.0')
        d.addCallbacks(lambda x: True, lambda x: False)
        return d

    def buildCollector(self, config, proxy, name, description):
        return KeepalivedCollector(config, proxy, name, description)

factory = KeepalivedCollectorFactory()
