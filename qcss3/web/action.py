"""
Action related pages
"""

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

    @RefreshMixIn.exist
    def data_json(self, ctx, data):
        return self.collector.actions(self.lb, self.vs, self.rs)
