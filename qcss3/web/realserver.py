from qcss3.web.json import JsonPage

class RealOrSorryServerResource(JsonPage):
    """
    Give the list of real servers or sorry servers

    For example::
       {"r1":["fofo02wb","ok"],
        "r2":["fofo03wb","ok"],
        "r3":["fofo04wb","disabled"],
        "r4":["fofo05wb","down"]}
    
    When the virtual server does not exist or the load balancer does
    not exist, the list is empty.

    The class attribute C{sorry} tells if we want the sorry servers or
    the real servers.
    """

    def __init__(self, lb, vs, dbpool, collector):
        self.lb = lb
        self.vs = vs
        self.dbpool = dbpool
        self.collector = collector
        if not hasattr(self, "sorry"):
            raise NotImplementedError
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        d = self.dbpool.runQueryInPast(ctx, """
SELECT rs.rs, rs.name, rs.rstate
FROM realserver rs
WHERE rs.deleted = 'infinity'
AND rs.lb = %%(lb)s
AND rs.vs = %%(vs)s
AND %s rs.sorry
""" % (not self.sorry and "NOT" or ""),
                                       {'lb': self.lb,
                                        'vs': self.vs})
        d.addCallback(self.format_json)
        return d

    def format_json(self, data):
        result = {}
        for rs, name, rstate in data:
            result[rs] = [name, rstate]
        return result

class RealServerResource(RealOrSorryServerResource):
    sorry = False

class SorryServerResource(RealOrSorryServerResource):
    sorry = True
