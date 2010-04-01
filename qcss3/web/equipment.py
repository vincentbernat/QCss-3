from qcss3.web.json import JsonPage

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

class LoadBalancerDetailResource(JsonPage):
    """
    Return details about a load balancer.

    For example::
      {"name": "loadbalancer1.example.com",
       "description": "Nortel Application Switch 2208",
       "type": "AAS"}
    """

    def __init__(self, name, dbpool, collector):
        self.name = name
        self.dbpool = dbpool
        self.collector = collector
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        d = self.dbpool.runQueryInPast(ctx, """
SELECT name, description, type
FROM loadbalancer
WHERE name=%(name)s
AND deleted='infinity'
""",
                                       {'name': self.name})
        d.addCallback(self.format_json)
        return d

    def format_json(self, data):
        if not data:
            # Not found, 404
            return None
        return {'name': data[0][0],
                'description': data[0][1],
                'type': data[0][2]}
