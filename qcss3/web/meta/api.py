"""
API related pages for metaweb
"""

from nevow import rend, tags as T, loaders

from qcss3.web.timetravel import IPastDate
from qcss3.web.meta.client import MetaClient
from qcss3.web.meta.past import MetaPastResource
from qcss3.web.meta.loadbalancer import MetaLoadBalancerResource
from qcss3.web.meta.search import MetaSearchResource
from qcss3.web.meta.status import StatusResource

class MetaApiResource(rend.Page):
    """
    API for metaweb.

    This API is similar to the standard one but will query several
    regular web services to build the answer.
    """

    addSlash = True
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])
    client = None

    def __init__(self, config):
        self.config = config
        if MetaApiResource.client is None:
            MetaApiResource.client = MetaClient(self.config)
        rend.Page.__init__(self)

    def child_past(self, ctx):
        # We should check if we already have a date, but it is not really useful here
        return MetaPastResource(self)

    def child_loadbalancer(self, ctx):
        return MetaLoadBalancerResource(self.client)

    def child_search(self, ctx):
        return MetaSearchResource(self.client)

    def child_status(self, ctx):
        return StatusResource(self.client)
