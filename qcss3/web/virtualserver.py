from qcss3.web.json import JsonPage

class VirtualServerResource(JsonPage):
    """
    Give the list of virtual servers.

    For example::
       {'v1g2s9': ["ForumsV4","193.252.117.114:80","ok"],
        'v1g2s10': ["ForumsV4","193.252.117.114:81","ok"],
        'v2g1s1': ["forum-rec.wanadooportails.com","193.252.111.12:80","degraded"]}

    For each virtual server, the first member of the tuple is the name
    of the virtual server, the second is the VIP and the last one is
    one of those values depending on the status of real servers:
     - ok       (no real server is down, at least one is up)
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
                result[vs] = [name, vip, rstate]
            else:
                cur = result[vs][2] # Current state (ok, disabled, down, degraded)
                if rstate == "ok":
                    if cur == "disabled":
                        result[vs][2] = "ok"
                        continue
                    if cur == "down":
                        result[vs][2] = "degraded"
                        continue
                    continue
                if rstate == "disabled":
                    continue
                if rstate == "down":
                    if cur == "ok":
                        result[vs][2] = "degraded"
                        continue
                    if cur == "disabled":
                        result[vs][2] = "down"
                        continue
                    continue
        return result
