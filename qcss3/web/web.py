from nevow import rend, appserver, loaders, page
from nevow import tags as T

from qcss3.web.api import ApiResource, ApiVersionedResource
from qcss3.web.meta.api import MetaApiResource

class MainPage(rend.Page):

    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])

    def __init__(self, *args):
        self.params = args
        rend.Page.__init__(self)

    def child_api(self, ctx):
        return ApiResource(self.getFactory(), *self.params)

    def getFactory(self):
        raise NotImplementedError

class WebMainPage(MainPage):
    def getFactory(self):
        return ApiVersionedResource

class MetaWebMainPage(MainPage):
    def getFactory(self):
        return MetaApiResource
