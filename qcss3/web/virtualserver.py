from qcss3.web.json import JsonPage
from qcss3.web.realserver import RealServerResource, SorryServerResource
from qcss3.web.refresh import RefreshResource, RefreshMixIn

def aggregate_state(states):
    if not states:
        return "up"
    state = states[0]
    for rstate in states[1:]:
        if rstate == "up":
            if state == "disabled":
                state = "up"
                continue
            if state == "down":
                state = "degraded"
                continue
            continue
        if rstate == "disabled":
            continue
        if rstate == "down":
            if state == "up":
                state = "degraded"
                continue
            if state == "disabled":
                state = "down"
                continue
            continue
    return state


class VirtualServerResource(JsonPage, RefreshMixIn):
    """
    Give the list of virtual servers.

    For example::
       {'v1g2s9': ["ForumsV4","193.252.117.114:80","up"],
        'v1g2s10': ["ForumsV4","193.252.117.114:81","up"],
        'v2g1s1': ["forum-rec.wanadooportails.com","193.252.111.12:80","degraded"]}

    For each virtual server, the first member of the tuple is the name
    of the virtual server, the second is the VIP and the last one is
    one of those values depending on the status of real servers:
     - up       (no real server is down, at least one is up)
     - disabled (all real servers are disabled)
     - down     (no real server is up, at least one is down)
     - degraded (one real server is down, one is up)

    When a virtual server has no real server, it won't appear
    here. When a load balancer does not exist, the list of virtual
    servers is empty.
    """

    def __init__(self, lb, dbpool, collector):
        self.lb = lb
        self.dbpool = dbpool
        self.collector = collector
        JsonPage.__init__(self)

    @RefreshMixIn.fresh
    def data_json(self, ctx, data):
        d = self.dbpool.runQueryInPast(ctx, """
SELECT vs.vs, vs.name, vs.vip, rs.rstate
FROM virtualserver vs, realserver rs
WHERE vs.lb = %(lb)s
AND rs.lb = vs.lb
AND rs.vs = vs.vs
AND NOT rs.sorry
AND vs.deleted = 'infinity'
AND rs.deleted = 'infinity'
""",
                                       {'lb': self.lb})
        d.addCallback(self.format_json)
        return d
        
    def format_json(self, data):
        result = {}
        for vs, name, vip, rstate in data:
            if vs not in result:
                result[vs] = [name, vip, [rstate]]
            else:
                result[vs][2].append(rstate)
        for vs in result:
            result[vs][2] = aggregate_state(result[vs][2])
        return result

    def childFactory(self, ctx, name):
        return VirtualServerDetailResource(self.lb,
                                           name,
                                           self.dbpool,
                                           self.collector)

class VirtualServerDetailResource(JsonPage, RefreshMixIn):
    """
    Give details about a virtual server.

    For example::
      {"name": "ForumsV4",
       "state": "up",
       "protocol": "tcp",
       "mode": "round robin",
       "VIP": " 193.252.117.114:80",
       "healthcheck": "http"}

    State is the same as in virtual server summary.
    """

    def __init__(self, lb, vs, dbpool, collector):
        self.lb = lb
        self.vs = vs
        self.dbpool = dbpool
        self.collector = collector
        JsonPage.__init__(self)

    def result_general(self, data):
        if not data:            # Does not exist
            self.results = None
        else:
            self.results = {"name": data[0][0],
                            "VIP": data[0][1],
                            "protocol": data[0][2],
                            "mode": data[0][3]}
        return self.results

    def result_state(self, data):
        if self.results is None:
            return None
        self.results["state"] = aggregate_state([x[0] for x in data])
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
    def data_json(self, ctx, data):
        d = self.dbpool.runQueryInPast(ctx, """
SELECT vs.name, vs.vip, vs.protocol, vs.mode
FROM virtualserver vs
WHERE vs.lb = %(lb)s
AND vs.vs = %(vs)s
AND vs.deleted = 'infinity'
""",
                                       {'lb': self.lb,
                                        'vs': self.vs})
        d.addCallback(self.result_general)
        d.addCallback(lambda x:
                          self.dbpool.runQueryInPast(ctx, """
SELECT rs.rstate
FROM realserver rs
WHERE rs.deleted='infinity'
AND rs.lb = %(lb)s
AND rs.vs = %(vs)s
AND NOT rs.sorry
""",
                                       {'lb': self.lb,
                                        'vs': self.vs}))
        d.addCallback(self.result_state)
        d.addCallback(lambda x:
                          self.dbpool.runQueryInPast(ctx, """
SELECT vs.key, vs.value
FROM virtualserver_extra vs
WHERE vs.deleted='infinity'
AND vs.lb = %(lb)s
AND vs.vs = %(vs)s
""",
                                       {'lb': self.lb,
                                        'vs': self.vs}))
        d.addCallback(self.result_extra)
        return d

    def child_realserver(self, ctx):
        return RealServerResource(self.lb, self.vs, self.dbpool, self.collector)

    def child_sorryserver(self, ctx):
        return SorryServerResource(self.lb, self.vs, self.dbpool, self.collector)

    def child_refresh(self, ctx):
        return RefreshResource(self.dbpool, self.collector,
                               self.lb, self.vs)
