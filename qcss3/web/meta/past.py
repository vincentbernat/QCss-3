"""
Past handling for metaweb
"""

from nevow import rend, tags as T, loaders

from qcss3.web.timetravel import IPastDate

class MetaPastResource(rend.Page):
    """
    Resource to register a date in the current context.

    No check is done on the date.
    """
    addSlash = True
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])
    def __init__(self, main):
        self.main = main
    def childFactory(self, ctx, date):
        ctx.remember(date, IPastDate)
        return self.main
