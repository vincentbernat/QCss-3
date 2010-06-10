"""
Search handling for metaweb
"""

from nevow import rend, loaders, tags as T

from qcss3.web.timetravel import IPastDate
from qcss3.web.json import JsonPage
from qcss3.web.common import IApiVersion

class MetaSearchResource(rend.Page):
    addSlash = True
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])
    def __init__(self, client):
        self.client = client
        rend.Page.__init__(self)
    def childFactory(self, ctx, name):
        return MetaSearchGenericResource(self.client, name)

class MetaSearchGenericResource(JsonPage):
    """
    Search a term accross all web services.
    """

    def __init__(self, client, term):
        self.client = client
        self.term = term
        JsonPage.__init__(self)

    def data_json(self, ctx, data):

        def process(data):
            results = []
            for rr in data:
                for r in rr:
                    if not r in results:
                        results.append(r)
            return results

        try:
            date = ctx.locate(IPastDate)
        except KeyError:
            date = None
        d = self.client.get_all(IApiVersion(ctx), date, "search", self.term)
        d.addCallback(process)
        return d
