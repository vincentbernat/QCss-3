"""
Collector for HAProxy 

 - MIB: EXCELIANCE-MIB
 - Supported hardware:
    - any host running HAProxy with EXCELIANCE-MIB bridge

Since it is difficult to link backends to frontends, we assume the
following convention: a backend is used by a frontend if it is
prefixed by the name of the frontend with a double dash. For example,
`frontend1` will use backends `frontend1`, `frontend1--static`,
`frontend1--dynamic`.

Moreover, if you want to get a VIP, the frontend should be named
VIP--frontend. The backend can then be named either VIP--frontend,
frontend, VIP--frontend--backend, frontend--backend...

To get the IP of a server, you also need to prefix its name with
it. For example 172.16.15.93--server.
"""

import re
import socket

from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.python import log
from zope.interface import implements

from qcss3.collector.icollector import ICollector, ICollectorFactory
from qcss3.collector.datastore import LoadBalancer, VirtualServer, RealServer, SorryServer
from generic import GenericCollector

class HAProxyCollector(GenericCollector):
    """
    Collect data for HAProxy
    """
    implements(ICollector)

    oids = dict(
        # Frontend
        alFrontendName='.1.3.6.1.4.1.23263.4.2.1.3.2.1.3',
        alFrontendStatus='.1.3.6.1.4.1.23263.4.2.1.3.2.1.13',
        # Backend
        alBackendName='.1.3.6.1.4.1.23263.4.2.1.3.3.1.3',
        alBackendStatus='.1.3.6.1.4.1.23263.4.2.1.3.3.1.20',
        alBackendDownTime='.1.3.6.1.4.1.23263.4.2.1.3.3.1.23',
        # Servers
        alServerName='.1.3.6.1.4.1.23263.4.2.1.3.4.1.4',
        alServerStatus='.1.3.6.1.4.1.23263.4.2.1.3.4.1.19',
        alServerWeight='.1.3.6.1.4.1.23263.4.2.1.3.4.1.21',
        alServerActive='.1.3.6.1.4.1.23263.4.2.1.3.4.1.22',
        alServerBackup='.1.3.6.1.4.1.23263.4.2.1.3.4.1.23',
        alServerDownTime='.1.3.6.1.4.1.23263.4.2.1.3.4.1.26',
        )

    kind = "HAProxy"

    def parse(self, vs=None, rs=None):
        """
        Parse vs and rs into pid, front, back, serv
        """
        if vs is not None:
            mo = re.match(r"p(\d)+,f(\d+)", vs)
            if not mo:
                raise ValueError("%r is not a valid virtual server" % vs)
            pid = int(mo.group(1))
            front = int(mo.group(2))
            if rs is not None:
                mo = re.match(r"b(\d+),s(\d+)", rs)
                if not mo:
                    raise ValueError("%r is not a valid real server" % rs)
                back = int(mo.group(1))
                serv = int(mo.group(2))
                return pid, front, back, serv
            return pid, front, None, None
        return None, None, None, None

    def collect(self, vs=None, rs=None):
        """
        Collect data for a HAProxy.

        Virtual server is PID + frontend. Real server is PID + backend + server
        """
        pid, front, back, serv = self.parse(vs, rs)
        if pid is not None:
            if back is not None:
                # Collect data to refresh a specific real server
                d = self.process_rs(pid, back, serv)
            else:
                # Collect data to refresh a virtual server
                d = self.process_vs(pid, front)
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
        for pid, front in self.cache('alFrontendName'):
            vs = defer.waitForDeferred(self.process_vs(pid, front))
            yield vs
            vs = vs.getResult()
            if vs is not None:
                self.lb.virtualservers["p%d,f%d" % (pid, front)] = vs
        yield self.lb
        return

    @defer.deferredGenerator
    def process_vs(self, pid, front):
        """
        Process data for a given virtual server when no real server is provided

        @param pid: process ID handling the virtual server
        @param front: frontend ID handling the virtual server
        @return: a deferred C{IVirtualServer} or None
        """
        # Retrieve some data if needed
        oids = []
        for o in self.oids:
            if o.startswith("alFrontend"):
                oids.append((o, pid, front))
        oids = tuple(oids)
        c = defer.waitForDeferred(self.cache_or_get(*oids))
        yield c
        c.getResult()

        fname = self.cache(('alFrontendName', pid, front))
        sfname = fname
        if "--" in fname:
            vip, sfname = fname.split("--", 1)
        else:
            vip = "unknown"
        vs = VirtualServer(sfname, vip, "unknown", "unknown")

        # Add some extra information
        vs.extra["status"] = self.cache(('alFrontendStatus', pid, front))

        # Find and attach real servers
        if not self.is_cached(('alBackendName', pid, 1)):
            backends = defer.waitForDeferred(
                self.proxy.walk("%s.%d" % (self.oids['alBackendName'], pid)))
            yield backends
            backends.getResult()
        for bid, bname in self.cache(('alBackendName', pid)).items():
            if bname == fname or \
                    bname.startswith("%s--" % fname) or \
                    bname.startswith("%s--" % sfname):
                # This backend matches. We need to fetch associated servers
                if not self.is_cached(('alServerName', pid, bid, 1)):
                    servers = defer.waitForDeferred(
                        self.proxy.walk("%s.%d.%d" % (self.oids['alServerName'], pid, bid)))
                    yield servers
                    servers.getResult()
                try:
                    servers = self.cache(('alServerName', pid, bid))
                except KeyError:
                    servers = None
                if not servers:
                    log.msg("In %r, for backend %s, no servers, skip it" % (self.lb.name, bname))
                    yield None
                    return
                for rid in servers:
                    # Fetch information for each real server
                    rs = defer.waitForDeferred(self.process_rs(pid, bid, rid))
                    yield rs
                    rs = rs.getResult()
                    if rs is not None:
                        vs.realservers["b%d,s%d" % (bid, rid)] = rs

        yield vs
        return

    @defer.deferredGenerator
    def process_rs(self, pid, bid, rid):
        """
        Process data for a given virtual server and real server.

        @param pid: process ID of the instance managing the real server
        @param bid: backend ID of the real server
        @param rid: server ID of the real server

        @return: a deferred C{IRealServer} or None
        """
        # Retrieve some data if needed:
        oids = []
        for o in self.oids:
            if o.startswith("alBackend"):
                oids.append((o, pid, bid))
            elif o.startswith("alServer"):
                oids.append((o, pid, bid, rid))
        oids = tuple(oids)
        c = defer.waitForDeferred(self.cache_or_get(*oids))
        yield c
        c.getResult()

        # Build the real server
        rip = "0.0.0.0"
        rport = None
        bname = self.cache(("alBackendName", pid, bid))
        rname = self.cache(("alServerName", pid, bid, rid))
        if "--" in rname:
            rip, rname = rname.split("--", 1)
            if ":" in rip:
                rip, rport = rip.split(":", 1)
                rport = int(rport)
        weight = self.cache(("alServerWeight", pid, bid, rid))
        state = self.cache(("alServerActive", pid, bid, rid)) and "up" or "down"
        backup = self.cache(("alServerBackup", pid, bid, rid))
        if not backup:
            rs = RealServer(rname, rip, rport, "unknown", weight, state)
        else:
            rs = SorryServer(rname, rip, rport, "unknown", state)
        down = self.cache(("alServerDownTime", pid, bid, rid))/100
        rs.extra["backend"] = bname
        rs.extra["down time"] = "%02d:%02d:%02d" % (down / 3600, (down / 60) % 60, down % 60)
        down = self.cache(("alBackendDownTime", pid, bid))/100
        rs.extra["backend down time"] = "%02d:%02d:%02d" % (down / 3600, (down / 60) % 60, down % 60)
        rs.extra["status"] = self.cache(("alServerStatus", pid, bid, rid))
        rs.extra["backend status"] = self.cache(("alBackendStatus", pid, bid))
        yield rs
        return

    @defer.deferredGenerator
    def execute(self, action, actionargs=None, vs=None, rs=None):
        """
        Execute an action.

        @param action: action to be executed
        """
        return

class HAProxyCollectorFactory:
    implements(ICollectorFactory, IPlugin)

    def canBuildCollector(self, proxy, description, oid):
        """
        Does this factory for HAProxy can build a collector for this agent?

        The OID is of no use here, we check that we have a HAProxy subagent.
        """
        # We check if there is at least one process in the alProcessTable
        d = proxy.get('.1.3.6.1.4.1.23263.4.2.1.3.1.1.1.1')
        d.addCallbacks(lambda x: True, lambda x: False)
        return d

    def buildCollector(self, config, proxy, name, description):
        return HAProxyCollector(config, proxy, name, description)

factory = HAProxyCollectorFactory()
