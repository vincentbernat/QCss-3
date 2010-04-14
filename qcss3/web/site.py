import os

from twisted.python import util
from zope.interface import implements
from nevow import rend, appserver, loaders, page
from nevow import tags as T
from nevow import static, inevow

from qcss3.web.api import ApiResource

class MainPage(rend.Page):

    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])

    def __init__(self, config, dbpool, collector):
        self.config = config
        self.dbpool = dbpool
        self.collector = collector
        rend.Page.__init__(self)

    def child_api(self, ctx):
        return ApiResource(self.config, self.dbpool, self.collector)
