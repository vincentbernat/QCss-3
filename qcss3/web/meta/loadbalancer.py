from qcss3.web.timetravel import IPastDate
from qcss3.web.json import JsonPage

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
        except:
            date = None
        return self.client.get_loadbalancers(date)
