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
                 lb=None, vs=None, rs=None):
        self.dbpool = dbpool
        self.collector = collector
        self.lb = lb
        self.vs = vs
        self.rs = rs
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        start = time.time()
        d = self.collector.refresh(self.lb, self.vs, self.rs)
        d.addCallback(lambda x: "Refreshed in %d second(s)" % int(time.time() - start))
        return d

