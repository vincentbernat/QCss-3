from qcss3.web.timetravel import IPastDate
from qcss3.web.json import JsonPage
from qcss3.web.meta.client import ProxyResource

class MetaLoadBalancerResource(JsonPage):
    """
    Return the list of available loadbalancers.
    """

    def __init__(self, client):
        self.client = client
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        try:
            date = ctx.locate(IPastDate)
        except KeyError:
            date = None
        return self.client.get_loadbalancers(date)

    def childFactory(self, ctx, lb):
        """
        Proxy any child request
        """
        return ProxyResource(lb, self.client)
