from twisted.internet import defer

from qcss3.web.json import JsonPage
from qcss3.web.refresh import RefreshMixIn

class ActionResource(JsonPage, RefreshMixIn):
    """
    Give the list of available actions for a given entity

    For example::
       { 'enable': 'Enable',
         'operenable': 'Enable (oper)' }
    """

    def __init__(self, dbpool, collector, lb, vs=None, rs=None, sorry=False):
        self.dbpool = dbpool
        self.collector = collector
        self.lb = lb
        self.vs = vs
        self.rs = rs
        self.sorry = sorry

    def data_json(self, ctx, data):

        def validate(x):
            if x is not None and x >= 0:
                return self.collector.actions(self.lb, self.vs, self.rs)
            return None

        d = defer.maybeDeferred(self.age, ctx, self.lb, self.vs, self.rs, self.sorry)
        d.addCallback(validate)
        return d
