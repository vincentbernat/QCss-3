"""
Realserver related pages
"""

from qcss3.web.json import JsonPage
from qcss3.web.refresh import RefreshResource, RefreshMixIn
from qcss3.web.action import ActionMixIn

class RealOrSorryServerResource(JsonPage, RefreshMixIn):
    """
    Give the list of real servers or sorry servers

    For example::
       {"r1":["fofo02wb","up"],
        "r2":["fofo03wb","up"],
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

    @RefreshMixIn.fresh
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

    def childFactory(self, ctx, name):
        return RealServerDetailResource(self.lb, self.vs, name,
                                        self.dbpool, self.collector)

class SorryServerResource(RealOrSorryServerResource):
    sorry = True

    def childFactory(self, ctx, name):
        return SorryServerDetailResource(self.lb, self.vs, name,
                                         self.dbpool, self.collector)

class RealOrSorryServerDetailResource(ActionMixIn, JsonPage, RefreshMixIn):
    """
    Give the details about a real server.

    For example::
       {"name": "fofo02wb",
        "IP: "172.16.78.164",
        "port": 80,
        "weight": 1,
        "state": "up",
        "check": "http",
        "frequency": "3s",
        "retry": 3,
        "timeout": 2}

    The class attribute C{sorry} tells if we want the sorry servers or
    the real servers.
    """

    def __init__(self, lb, vs, rs, dbpool, collector):
        self.lb = lb
        self.vs = vs
        self.rs = rs
        self.dbpool = dbpool
        self.collector = collector
        if not hasattr(self, "sorry"):
            raise NotImplementedError
        JsonPage.__init__(self)

    def result_general(self, data):
        if not data:            # Does not exist
            self.results = None
        else:
            self.results = {"name": data[0][0],
                            "IP": data[0][1],
                            "port": data[0][2],
                            "protocol": data[0][3],
                            "state": data[0][5]}
            if not self.sorry:
                self.results["weight"] = data[0][4]
        return self.results

    def result_extra(self, data):
        if self.results is None:
            return None
        for key, value in data:
            if key not in self.results: # Don't overwrite more important values
                try:
                    self.results[key] = int(value)
                except ValueError:
                    self.results[key] = value
        return self.results

    @RefreshMixIn.fresh
    @ActionMixIn.actions
    def data_json(self, ctx, data):
        d = self.dbpool.runQueryInPast(ctx, """
SELECT rs.name, rs.rip, rs.port, rs.protocol, rs.weight, rs.rstate
FROM realserver rs
WHERE rs.lb = %%(lb)s
AND rs.vs = %%(vs)s
AND rs.rs = %%(rs)s
AND rs.deleted = 'infinity'
AND %s rs.sorry
""" % (not self.sorry and "NOT" or ""),
                                       {'lb': self.lb,
                                        'vs': self.vs,
                                        'rs': self.rs})
        d.addCallback(self.result_general)
        d.addCallback(lambda x:
                          self.dbpool.runQueryInPast(ctx, """
SELECT rs.key, rs.value
FROM realserver_extra rs
WHERE rs.deleted='infinity'
AND rs.lb = %(lb)s
AND rs.vs = %(vs)s
AND rs.rs = %(vs)s
""",
                                       {'lb': self.lb,
                                        'vs': self.vs,
                                        'rs': self.rs}))
        d.addCallback(self.result_extra)
        return d

    def child_refresh(self, ctx):
        return RefreshResource(self.dbpool, self.collector,
                               self.lb, self.vs, self.rs, self.sorry)

class RealServerDetailResource(RealOrSorryServerDetailResource):
    sorry = False

class SorryServerDetailResource(RealOrSorryServerDetailResource):
    sorry = True
