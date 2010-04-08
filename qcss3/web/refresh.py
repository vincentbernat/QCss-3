import time

from qcss3.web.json import JsonPage

class RefreshResource(JsonPage):
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
        if self.lb:
            if self.vs:
                if self.rs:
                    d = self.dbpool.runQuery("""
SELECT COUNT(1)
FROM realserver
WHERE lb=%%(lb)s
AND vs=%%(vs)s
AND rs=%%(rs)s
AND %s sorry
AND deleted='infinity'
""" % (not self.sorry and "NOT" or ""),
                                                   {'lb': self.lb,
                                                    'vs': self.vs,
                                                    'rs': self.rs})
                else:
                    d = self.dbpool.runQuery("""
SELECT COUNT(1)
FROM virtualserver
WHERE lb=%(lb)s
AND vs=%(vs)s
AND deleted='infinity'
""",
                                                   {'lb': self.lb,
                                                    'vs': self.vs})
            else:
                d = self.dbpool.runQuery("""
SELECT COUNT(1)
FROM loadbalancer
WHERE name=%(lb)s
AND deleted='infinity'
""",
                                         {'lb': self.lb})
            d.addCallback(lambda x: self.refresh(x[0][0] == 1))
            return d
        return self.refresh()

    def refresh(self, refresh=True):
        if not refresh:
            return None
        start = time.time()
        d = self.collector.refresh(self.lb, self.vs, self.rs)
        d.addCallback(lambda x: "Refreshed in %d second(s)" % int(time.time() - start))
        return d

