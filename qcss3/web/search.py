"""
Search module.

This module allows to search into database. It uses brute-force
searching: search term is matched against each field of the
database. Optimisations may have to be done later.
"""

import socket

from twisted.internet import defer
from nevow import rend, loaders
from nevow import tags as T

from qcss3.web.json import JsonPage
from qcss3.web.common import IApiVersion

class SearchResource(rend.Page):

    addSlash = True
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])

    def __init__(self, dbpool):
        self.dbpool = dbpool
        rend.Page.__init__(self)

    def childFactory(self, ctx, name):
        """
        Dispatch the search to the generic search handler.
        """
        return SearchGenericResource(self.dbpool, name)

class SearchIn:
    """
    Generic search facility.

    To use this class, C{query} should be implemented to return a
    query that should return URL (without prefix) of matching
    results. The URL will be prefixed by API version.
    """
    

    def __init__(self, dbpool, term):
        self.term = term
        self.dbpool = dbpool

    def query(self):
        raise NotImplementedError

    def search(self, ctx):
        """
        Run the search query and prefix the results with API URL.
        """
        api = IApiVersion(ctx)
        d = self.dbpool.runQueryInPast(ctx,
                                       self.query(), {'term': self.term})
        d.addCallback(lambda results:
                          ["/api/%s/%s" % (api, y[0]) for y in results])
        return d

class SearchInLoadBalancer(SearchIn):
    """
    Search the term in C{loadbalancer} table.
    """

    def query(self):
       return """
SELECT 'loadbalancer/' || name || '/'
FROM loadbalancer
WHERE deleted='infinity'
AND (name ILIKE '%%'||%(term)s||'%%'
 OR  description ILIKE '%%'||%(term)s||'%%'
 OR  type ILIKE '%%'||%(term)s||'%%')
"""

class SearchInVirtualServer(SearchIn):
    """
    Search the term in C{virtualserver} table (name, vip and mode).
    """

    def query(self):
        return """
SELECT 'loadbalancer/' || lb || '/virtualserver/' || vs || '/'
FROM virtualserver
WHERE deleted='infinity'
AND (name ILIKE '%%'||%(term)s||'%%'
 OR  vip ILIKE '%%'||%(term)s||'%%'
 OR  mode ILIKE '%%'||%(term)s||'%%')
"""

class SearchInVirtualServerExtra(SearchIn):
    """
    Search the term in C{virtualserver_extra} table.
    """

    def query(self):
        return """
SELECT 'loadbalancer/' || lb || '/virtualserver/' || vs || '/'
FROM virtualserver_extra
WHERE deleted='infinity'
AND value ILIKE '%%'||%(term)s||'%%'
"""

class SearchInRealServer(SearchIn):
    """
    Search the term in C{realserver} table (name, rip).
    """

    def query(self):
        return """
SELECT 'loadbalancer/' || lb || '/virtualserver/' || vs || '/realserver/' || rs || '/'
FROM realserver
WHERE deleted='infinity'
AND (name ILIKE '%%'||%(term)s||'%%'
 OR  rip::text ILIKE '%%'||%(term)s||'%%')
"""

class SearchInRealServerExtra(SearchIn):
    """
    Search the term in C{realserver_extra} table.
    """

    def query(self):
        return """
SELECT 'loadbalancer/' || lb || '/virtualserver/' || vs || '/realserver/' || rs || '/'
FROM realserver_extra
WHERE deleted='infinity'
AND value ILIKE '%%'||%(term)s||'%%'
"""

class SearchGenericResource(JsonPage):
    """
    Generic search handler.

    This handler will search the term in various tables of the database.
    """

    # List of search handlers
    handlers = [
        SearchInLoadBalancer,
        SearchInVirtualServer,
        SearchInVirtualServerExtra,
        SearchInRealServer,
        SearchInRealServerExtra,
        ]

    def __init__(self, dbpool, term):
        self.term = term
        self.dbpool = dbpool
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        """
        List through the search handlers to output JSon data
        """
        l = []
        for s in self.handlers:
            l.append(s(self.dbpool, self.term).search(ctx))
        d = defer.DeferredList(l, consumeErrors=True)
        d.addCallback(self.flattenList)
        return d

    def flattenList(self, data):
        """
        Flatten a list from C{defer.DeferredList}.

        The list is also dedupped.
        """
        result = []
        for (success, value) in data:
            if success:
                for r in value:
                    result.append(r)
            else:
                print "While searching for %r, got:" % self.term
                value.printTraceback()
        # Remove dupes
        keys = {}
        for e in result:
            keys[e] = 1
        return keys.keys()

