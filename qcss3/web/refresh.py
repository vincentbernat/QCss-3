import time

from twisted.internet import defer
from twisted.python import log

from qcss3.web.json import JsonPage
from qcss3.web.timetravel import IPastDate

class RefreshMixIn:

    def isfresh(self, age, lb=None, vs=None, rs=None):
        """
        Does a given resource needs to be refreshed?

        @param age: age of the resource
        @return: C{True} if the resource does not need to be refreshed
        """
        if rs:
            return age < 10
        if vs:
            return age < 300
        if lb:
            return age < 300
        return True

    @classmethod
    def fresh(cls, f):
        """
        Decorator to ensure that data is fresh.

        The decorated function returns a deferred. It will return
        C{None} if the resource does not exist.

        @param f: a function whose first arguments are self and a context
        @return: C{f} decorated to refresh data if needed
        """
        def wrapped(self, ctx, *args, **kwargs):

            def tryrefresh(age):
                if age is None:
                    return None
                if not self.isfresh(age, self.lb, vs, rs):
                    d = self.refresh(self.lb, vs, rs)
                    d.addErrback(lambda x: log.msg("unable to autorefresh: %s" % x.value))
                    d.addCallback(lambda x: f(self, ctx, *args, **kwargs))
                return f(self, ctx, *args, **kwargs)

            vs = hasattr(self, "vs") and self.vs or None
            rs = hasattr(self, "rs") and self.rs or None
            sorry = rs is not None and self.sorry
            d = defer.maybeDeferred(self.age, ctx, self.lb, vs, rs, sorry)
            d.addCallback(tryrefresh)
            return d
        return wrapped

    def age(self, ctx, lb=None, vs=None, rs=None, sorry=False):
        """
        Return the age of the given resource.

        If in past, the age is -1 (because the data is current). If no
        loadbalancer is specified, the data is considered not current
        and therefore a very large value is returned.

        @return: the age of the resource and None if the resource does
            not exist.
        """
        try:
            date = ctx.locate(IPastDate)
            return -1
        except KeyError:
            pass
        if lb:
            if vs:
                if rs:
                    d = self.dbpool.runQuery("""
SELECT EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - updated)::int
FROM realserver
WHERE lb=%%(lb)s
AND vs=%%(vs)s
AND rs=%%(rs)s
AND %s sorry
AND deleted='infinity'
""" % (not sorry and "NOT" or ""),
                                                   {'lb': lb,
                                                    'vs': vs,
                                                    'rs': rs})
                else:
                    d = self.dbpool.runQuery("""
SELECT EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - updated)::int
FROM virtualserver
WHERE lb=%(lb)s
AND vs=%(vs)s
AND deleted='infinity'
""",
                                                   {'lb': lb,
                                                    'vs': vs})
            else:
                d = self.dbpool.runQuery("""
SELECT EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - updated)::int
FROM loadbalancer
WHERE name=%(lb)s
AND deleted='infinity'
""",
                                         {'lb': lb})
            d.addCallback(lambda x: len(x) > 0 and x[0][0] or None)
            return d
        # No resource specified, age is maximum
        return int(time.time())

    def refresh(self, lb=None, vs=None, rs=None):
        start = time.time()
        d = self.collector.refresh(lb, vs, rs)
        d.addCallback(lambda x: "Refreshed in %d second(s)" % int(time.time() - start))
        return d

class RefreshResource(JsonPage, RefreshMixIn):
    """
    Refresh a resource.

    The resource to be refreshed can be:
     - all load balancers
     - one load balancer
     - one virtual server
     - one real server
    """

    def __init__(self, dbpool, collector,
                 lb=None, vs=None, rs=None, sorry=False):
        self.dbpool = dbpool
        self.collector = collector
        self.lb = lb
        self.vs = vs
        self.rs = rs
        self.sorry = sorry
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        d = defer.maybeDeferred(self.age, ctx, self.lb, self.vs, self.rs, self.sorry)
        d.addCallback(lambda x: x is not None and x >= 0 and
                      self.refresh(self.lb, self.vs, self.rs) or None)
        return d

