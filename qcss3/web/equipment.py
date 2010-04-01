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
