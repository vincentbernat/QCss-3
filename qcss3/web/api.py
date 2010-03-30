from nevow import rend, tags as T, loaders

from qcss3.web.timetravel import PastResource, IPastDate, PastConnectionPool
from qcss3.web.common import IApiVersion

class ApiResource(rend.Page):
    """
    Web service for QCss3.
    """

    addSlash = True
    versions = [ "1.0" ]        # Valid versions
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Valid versions are:" ],
                                   T.ul [ [ T.li[v] for v in versions ] ] ] ])

    def __init__(self, config, dbpool, collector):
        self.config = config
        self.dbpool = dbpool
        self.collector = collector
        rend.Page.__init__(self)

    def childFactory(self, ctx, version):
        if version in ApiResource.versions:
            ctx.remember(version, IApiVersion)
            return ApiVersionedResource(self.config, self.dbpool, self.collector)
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

    def child_refresh(self, ctx):
        self.collector.refresh()
        p = rend.Page(docFactory=loaders.stan(T.html [ T.body [
                        T.p ["Refresh started"] ] ]))
        p.addSlash = True
        return p

    def child_past(self, ctx):
        try:
            # Check if we already got a date
            ctx.locate(IPastDate)
        except KeyError:
            return PastResource(self)
        return None
