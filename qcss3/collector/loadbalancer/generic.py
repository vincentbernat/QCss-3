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

    def collect(self, vs=None, rs=None):
        data = {}
        d = defer.succeed(True)
        for oid in self.oids:
            d.addCallback(lambda x, oid: self.proxy.walk(self.oids[oid]), oid)
            d.addCallback(lambda x, oid: data.update({oid: self.trim(x, oid)}),
                          oid)
        d.addCallback(lambda x: self.process(data, vs, rs))
        return d

    def process(self, data, vs=None, rs=None):
        raise NotImplementedError

    def trim(self, mapping, oid):
        """
        Trim the prefix of a mapping from numerical OID to
        values. This function allows to keep only the index part of an
        OID. For example, consider the following example::

        >>> self.oids = {
        ... 'slbCurCfgVirtServerVname': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.2.1.10',
        ... 'slbCurCfgVirtServerState': '.1.3.6.1.4.1.1872.2.5.4.1.1.4.2.1.4',
        ... }
        >>> self.trim({'.1.3.6.1.4.1.1872.2.5.4.1.1.4.2.1.10.5': 'name1',
        ...            '.1.3.6.1.4.1.1872.2.5.4.1.1.4.2.1.10.7': 'name2',
        ...            '.1.3.6.1.4.1.1872.2.5.4.1.1.4.2.1.10.8': 'name3'},
        ...            'slbCurCfgVirtServerVname')
        {'.5': 'name1', '.7': 'name2', '.8': 'name3'}

        @param mapping: a mapping between a numerical OID and the
            value of this OID
        @param oid: name of an OID which should be a key of C{oids}
        @return: a mapping between the suffix of the numerical OID and
           the value.
        """
        result = {}
        for o in mapping:
            prefix = self.oids[oid]
            if not o.startswith(prefix):
                raise ValueError("Numerical OID %s should start with %s" % (o, prefix))
            result[o[len(prefix):]] = mapping[o]
        return result
