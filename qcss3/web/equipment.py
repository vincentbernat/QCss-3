from qcss3.web.json import JsonPage
from qcss3.web.virtualserver import VirtualServerResource
from qcss3.web.refresh import RefreshResource, RefreshMixIn
from qcss3.web.action import ActionResource

class LoadBalancerResource(JsonPage):
    """
    Give the list of load balancers.

    For example::
     ["loadbalancer1.example.net",
      "loadbalancer2.example.net",
      "loadbalancer3.example.net"]
    """

    def __init__(self, dbpool, collector):
        self.dbpool = dbpool
        self.collector = collector
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        d = self.dbpool.runQueryInPast(ctx,
                                       "SELECT name FROM loadbalancer "
                                       "WHERE deleted='infinity' "
                                       "ORDER BY name")
        d.addCallback(lambda x: [y[0] for y in x])
        return d

    def childFactory(self, ctx, name):
        return LoadBalancerDetailResource(name, self.dbpool, self.collector)

class LoadBalancerDetailResource(JsonPage, RefreshMixIn):
    """
    Return details about a load balancer.

    For example::
      {"name": "loadbalancer1.example.com",
       "description": "Nortel Application Switch 2208",
       "type": "AAS"}
    """

    def __init__(self, name, dbpool, collector):
        self.lb = name
        self.dbpool = dbpool
        self.collector = collector
        JsonPage.__init__(self)

    @RefreshMixIn.fresh
    def data_json(self, ctx, data):
        d = self.dbpool.runQueryInPast(ctx, """
SELECT name, description, type
FROM loadbalancer
WHERE name=%(name)s
AND deleted='infinity'
""",
                                       {'name': self.lb})
        d.addCallback(self.format_json)
        return d

    def format_json(self, data):
        if not data:
            # Not found, 404
            return None
        return {'name': data[0][0],
                'description': data[0][1],
                'type': data[0][2]}

    def child_virtualserver(self, ctx):
        return VirtualServerResource(self.lb,
                                     self.dbpool,
                                     self.collector)

    def child_action(self, ctx):
        return ActionResource(self.dbpool, self.collector, self.lb)

    def child_refresh(self, ctx):
        return RefreshResource(self.dbpool, self.collector,
                               self.lb)
