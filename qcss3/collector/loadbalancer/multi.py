"""
Special collector aggregating several collectors to produce one collector.
"""

import re

from twisted.plugin import IPlugin
from twisted.internet import defer
from twisted.python import log
from zope.interface import implements

from qcss3.collector.icollector import ICollector, ICollectorFactory
from qcss3.collector.datastore import LoadBalancer, VirtualServer, RealServer, SorryServer

class MultiCollector:
    """
    Collect data using multiple collectors
    """
    implements(ICollector)

    def __init__(self, config, proxy, name, description, plugins):
        self.name = name
        self.description = description
        self.config = config
        self.proxy = proxy
        self.collectors = {}
        for p in plugins:
            collector = p.buildCollector(config, proxy, name, description)
            self.collectors[p] = collector

    def collect(self, vs, rs):

        def packresults(results):
            kinds = []
            extra = {}
            actions = {}
            virtualservers = {}
            for (success, value) in results:
                if not success: # An errback has been fired in this case
                    continue
                kinds.append(value.kind)
                extra.update([("%s@%s" % (k, value.kind), v)
                              for (k,v) in value.extra.items()])
                actions.update([("%s@%s" % (k, value.kind), v)
                                for (k,v) in value.actions.items()])
                virtualservers.update([("%s@%s" % (k, value.kind), v)
                                       for (k,v) in value.virtualservers.items()])
            lb = LoadBalancer(self.name, " + ".join(kinds), self.description)
            lb.extra = extra
            lb.actions = actions
            lb.virtualservers = virtualservers
            return lb

        if vs is None:
            # Collect all load balancers
            d = defer.DeferredList([collector.collect(None, None)
                                    for collector in self.collectors.values()])
            d.addCallback(packresults)
            return d
        # Collect a given virtual server. Let's spot the collector that handles it
        rvs, rkind = vs.rsplit("@", 1)
        for c in self.collectors:
            if self.collectors[c].kind == rkind:
                return self.collectors[c].collect(rvs, rs)

    def execute(self, action, actionargs=None, vs=None, rs=None):
        if vs is None:
            # Actions are suffixed by the backend to use
            raction, rkind = action.rsplit("@", 1)
            for c in self.collectors:
                if self.collectors[c].kind == rkind:
                    return self.collectors[c].execute(raction, actionargs, None, None)
        else:
            # Action for a given virtual server
            rvs, rkind = vs.rsplit("@", 1)
            for c in self.collectors:
                if self.collectors[c].kind == rkind:
                    return self.collectors[c].execute(action, actionargs, rvs, rs)

class MultiCollectorFactory:
    """
    Factory for a collector able to handle multiple equipments.

    For example, keepalived and haproxy can live on the same
    host. This collector does not act as a plugin. It needs to be
    initialized with the list of plugins it should handle.
    """
    implements(ICollectorFactory)

    def __init__(self, plugins):
        self.plugins = plugins

    def canBuildCollector(self, proxy, description, oid):
        """
        This factory cannot be used automatically. It should be used only manually.
        """
        return False

    def buildCollector(self, config, proxy, name, description):
        return MultiCollector(config, proxy, name, description, self.plugins)
