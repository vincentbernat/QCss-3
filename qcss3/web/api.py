from nevow import rend, tags as T, loaders

from qcss3.web.timetravel import PastResource, IPastDate, PastConnectionPool
from qcss3.web.search import SearchResource
from qcss3.web.equipment import LoadBalancerResource
from qcss3.web.refresh import RefreshResource
from qcss3.web.common import IApiVersion

class ApiResource(rend.Page):
    """
    Web service for QCss3.
    """

    addSlash = True
    versions = [ "1.0" ]        # Valid versions
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Valid versions are:" ],
                                   T.ul [ [ T.li[v] for v in versions ] ] ] ])

    def __init__(self, api, *args):
        self.api = api
        self.params = args
        rend.Page.__init__(self)

    def childFactory(self, ctx, version):
        if version in ApiResource.versions:
            ctx.remember(version, IApiVersion)
            return self.api(*self.params)
        return None

class ApiVersionedResource(rend.Page):
    """
    Versioned web service for QCss3.
    """

    addSlash = True
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])

    def __init__(self, config, dbpool, collector):
        self.config = config
        self.dbpool = PastConnectionPool(dbpool)
        self.collector = collector
        rend.Page.__init__(self)

    def child_past(self, ctx):
        try:
            # Check if we already got a date
            ctx.locate(IPastDate)
        except KeyError:
            return PastResource(self)
        return None

    def child_loadbalancer(self, ctx):
        return LoadBalancerResource(self.dbpool, self.collector)

    def child_search(self, ctx):
        return SearchResource(self.dbpool)

    def child_refresh(self, ctx):
        return RefreshResource(self.dbpool, self.collector)
