"""
Status pages for metaweb
"""

from qcss3.web.json import JsonPage
from qcss3.web.timetravel import IPastDate

class StatusResource(JsonPage):
    """
    Return a status page with the current status of the metaweb
    backend.

    This status is just the list of load balancers and the associated
    services for the current date (this resource can be queried in the
    past).
    """

    def __init__(self, client):
        self.client = client
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        try:
            date = ctx.locate(IPastDate)
        except KeyError:
            date = None
        if date in self.client.loadbalancers:
            return self.client.loadbalancers[date]
        return {}

class PingResource(JsonPage):
    """
    Return a page where each backend is listed along with their status.
    (up or down).

    This resource cannot be queried in the past.
    """

    def __init__(self, client):
        self.client = client
        JsonPage.__init__(self)

    def data_json(self, ctx, data):
        # Not available in the past
        try:
            date = ctx.locate(IPastDate)
            return None
        except KeyError:
            pass
        result = {}
        loadbalancers = self.client.loadbalancers.get(None, {})
        for service in self.client.services:
            # Is the service attached to a load balancer?
            for lb in loadbalancers:
                if service in loadbalancers[lb]:
                    result[service] = 'up'
            if service not in result:
                result[service] = 'down'
        return result
