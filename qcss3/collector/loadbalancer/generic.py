"""
Generic collector.

This module provides a generic collector which implements some useful
methods to be used by more specific collectors. It is not a complete
collector.

There are also two helpers function to convert strings to OID and
vice-versa.
"""

from twisted.internet import defer

from qcss3.collector.datastore import LoadBalancer

def str2oid(string):
    """
    Convert the given string into an OID (as a string)

    It is assumed that the string is a variable-length string and
    therefore the OID is prefixed by its length.

    @param string: string to convert
    @return: OID as a string (not a tuple!)
    """
    oid = ".".join([str(ord(a)) for a in string])
    return "%d.%s" % (len(string), oid)

def oid2str(oid):
    """
    Convert the given OID (as a list) into a string.

    It is assumed that the string is variable length and therefore the
    OID is prefixed by the length of the string. If several strings
    are found into the oid, they are returned as a list of
    strings. Otherwise, only the string is returned.

    @param oid: OID to convert (as a tuple, not a string!)
    @return: a string or a list of strings
    """
    results = []
    if not oid:
        raise ValueError("Cannot convert empty OID")
    while oid:
        length = oid[0]
        if len(oid) - 1 < length:
            raise ValueError(
                "Cannot convert OID %r into a string due to incompatible length" % oid)
        result = "".join([chr(a) for a in oid[1:length+1]])
        results.append(result)
        oid = oid[length+1:]
    if len(results) > 1:
        return results
    return results[0]

class GenericCollector:
    """
    Helper functions for a collector.

    This generic collector needs several class variables:
     - C{oids} should be a mapping between OID names and numerical OID.
     - C{kind} should be a string defining the kind of load balancer
    """

    def __init__(self, config, proxy, name, description):
        self.config = config
        self.proxy = proxy
        self.lb = LoadBalancer(name, self.kind, description)

    def _extend_oids(self, *oids):
        newoids = []
        for o in oids:
            if type(o) is not tuple:
                newoids.append(self.oids[o])
            else:
                no = [self.oids[o[0]]]
                no.extend(o[1:])
                newoids.append(tuple(no))
        return tuple(newoids)

    def is_cached(self, *oids):
        try:
            r = self.cache(*oids)
        except KeyError:
            return False
        if type(r) is list:
            for k in r:
                if k is None:
                    return False
        return True

    @defer.deferredGenerator
    def cache_or_get(self, *oids):
        if self.is_cached(*oids):
            yield self.cache(*oids)
            return
        else:
            g = defer.waitForDeferred(self.proxy.get(list(self._extend_oids(*oids))))
            yield g
            g.getResult()
            yield self.cache(*oids)
            return

    def cache(self, *oids):
        """
        Retrieve OID from proxy cache. First member of each provided
        OID is fetched from OID dictionary.
        """
        oids = self._extend_oids(*oids)
        return self.proxy.cache(*oids)

    def bitmap(self, bitmap):
        for i in range(len(bitmap)):
            if bitmap[i] == '\x00':
                continue
            for r in range(8):
                if not ord(bitmap[i]) & (1 << r):
                    continue
                r = 8-r + i*8
                yield r
