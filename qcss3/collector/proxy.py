"""
SNMP proxy
"""

import snmp
from snmp import AgentProxy as original_AgentProxy
from twisted.internet import defer

def translateOid(oid):
    return [int(x) for x in oid.split(".") if x]

class WalkAgentProxy(original_AgentProxy):
    """Act like AgentProxy but handles walking itself"""

    use_getbulk = True

    def getbulk(self, oid, *args):
        if self.use_getbulk and self.version == 2:
            return original_AgentProxy.getbulk(self, oid, *args)
        d = self.getnext(oid)
        d.addErrback(lambda x: x.trap(snmp.SNMPEndOfMibView,
                                      snmp.SNMPNoSuchName) and {})
        return d

    def walk(self, oid):
        """
        Real walking.
        
        Return the list of oid retrieved
        """
        return Walker(self, oid)()

class AgentProxy(WalkAgentProxy):
    """
    Intelligent SNMP proxy.

    Features:
      - GET, GETBULK, GETNEXT
      - WALK
      - cache results
      - SET with a different proxy

    Each operation can an OID or a list of OID. Each OID can be a
    string or a tuple. In this case, the tuple elements will be
    concated. Some examples:
     - ".1.3.6.1.2.1.1.1.0"
     - [".1.3.6.1.2.1.1.1.0", ]
     - [".1.3.6.1.2.1.1.1.0", ".1.3.6.1.2.1.1.3.0"]
     - (".1.3.6.1.2.1.1.1", "0")
     - [(".1.3.6.1.2.1.1", 1, 0), ".1.3.6.1.2.1.1.3.0"]
    """

    def __init__(self, *args, **kwargs):
        self._cache = {}
        self._wproxy = None     # Write proxy
        if "wcommunity" in kwargs:
            self._wcommunity = kwargs["wcommunity"]
            del kwargs["wcommunity"]
        else:
            self._wcommunity = None
        return WalkAgentProxy.__init__(self, *args, **kwargs)

    def _normalize_oid(f):
        def new_f(self, oid, *args):
            if type(oid) is tuple:
                oid = ".".join([str(a) for a in oid])
            elif type(oid) is list:
                for i in range(len(oid)):
                    if type(oid[i]) is tuple:
                        oid[i] = ".".join([str(a) for a in oid[i]])
            return f(self, oid, *args)
        return new_f

    def _cache_results(f):
        def new_f(self, oid, *args):
            d = f(self, oid, *args)
            d.addCallback(lambda x: self._cache.update(x) or x)
            return d
        return new_f

    @_normalize_oid
    def _really_cache(self, oid):

        def str2tuple(oid):
            oid = tuple([int(o) for o in oid.split(".")])
            if len(oid) == 1:
                return oid[0]
            return oid

        c = self._cache.get(oid, None)
        if c is not None:
            return self._cache[oid]
        # Check if we have a prefix
        r = [(str2tuple(c[(len(oid)+1):]), self._cache[c])
             for c in self._cache
             if c.startswith("%s." % oid)]
        if not r:
            raise KeyError("%r is not available in cache" % oid)
        return dict(r)

    def cache(self, *oid):
        """
        Return an OID from the cache.

        The cache is queried for prefix if a requested OID is not
        found. This allows to use a for loop.

        A trimmed dictionary is a dictionary whose keys have been
        prefix-stripped and converted to a tuple of integers or to a
        simple integer.

        @param oid: an OID
        @return: A value for an exact match or a trimmed dictionary
           for prefix match. If several OID are asked, return a list.
        """
        if len(oid) > 1:
            r = []
            for o in oid:
                try:
                    r.append(self._really_cache(o))
                except KeyError:
                    r.append(None)
            return r
        return self._really_cache(oid[0])

    @_normalize_oid
    def set(self, *args, **kwargs):
        """
        Set a value using SNMP SET.

        A specific proxy is used for this operation since we need a
        different community. This operation is only available if we
        have a write community.
        """
        if self._wcommunity is None:
            raise TypeError("no write community is defined")
        if self._wproxy is None:
            # We should instiante a write proxy
            self._wproxy = WalkAgentProxy(self.ip, self._wcommunity, self.version)
        return self._wproxy.set(*args, **kwargs)

    get     = _cache_results(_normalize_oid(WalkAgentProxy.get))
    # getbulk and getnext are not cached because we could cache results that we don't want
    getnext = _normalize_oid(WalkAgentProxy.getnext)
    getbulk = _normalize_oid(WalkAgentProxy.getbulk)
    walk    = _cache_results(_normalize_oid(WalkAgentProxy.walk))
        
class Walker(object):
    """SNMP walker class"""

    def __init__(self, proxy, baseoid):
        self.baseoid = baseoid
        self.lastoid = baseoid
        self.proxy = proxy
        self.results = {}
        self.defer = defer.Deferred()

    def __call__(self):
        d = self.proxy.getbulk(self.baseoid)
        d.addErrback(lambda x: x.trap(snmp.SNMPEndOfMibView,
                                      snmp.SNMPNoSuchName) and {})
        d.addCallback(self.getMore)
        d.addErrback(self.fireError)
        return self.defer

    def getMore(self, x):
        stop = False
        for o in x:
            if o in self.results:
                stop = True
                continue
            if translateOid(o)[:len(translateOid(self.baseoid))] != \
                    translateOid(self.baseoid):
                stop = True
                continue
            self.results[o] = x[o]
            if translateOid(self.lastoid) < translateOid(o):
                self.lastoid = o
        if stop or not x:
            self.defer.callback(self.results)
            self.defer = None
            return
        d = self.proxy.getbulk(self.lastoid)
        d.addErrback(lambda x: x.trap(snmp.SNMPEndOfMibView,
                                      snmp.SNMPNoSuchName) and {})
        d.addCallback(self.getMore)
        d.addErrback(self.fireError)
        return None

    def fireError(self, error):
        self.defer.errback(error)
        self.defer = None

        
