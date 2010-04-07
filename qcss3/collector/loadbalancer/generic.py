"""
Generic collector.

This module provides a generic collector which implements some useful
methods to be used by more specific collectors. It is not a complete
collector.
"""

from twisted.internet import defer

from qcss3.collector.datastore import LoadBalancer

class GenericCollector:
    """
    Generic collector

    This generic collector needs several class variables:
     - C{oids} should be a mapping between OID names and numerical OID.
     - C{kind} should be a string defining the kind of load balancer
     - C{process} should be implemented
    """

    def __init__(self, config, proxy, name, description):
        self.config = config
        self.proxy = proxy
        self.lb = LoadBalancer(name, self.kind, description)

    def cache(self, *oids):
        """
        Retrieve OID from proxy cache. First member of each provided
        OID is fetched from OID dictionary.
        """
        newoids = []
        for o in oids:
            if type(o) is not tuple:
                newoids.append(self.oids[o])
            else:
                no = [self.oids[o[0]]]
                no.extend(o[1:])
                newoids.append(tuple(no))
        newoids = tuple(newoids)
        return self.proxy.cache(*newoids)

    def collect(self, vs=None, rs=None):
        d = defer.succeed(True)
        for oid in self.oids:
            d.addCallback(lambda x, oid: self.proxy.walk(self.oids[oid]), oid)
        d.addCallback(lambda x: self.process(vs, rs))
        return d

    def process(self, vs=None, rs=None):
        raise NotImplementedError
