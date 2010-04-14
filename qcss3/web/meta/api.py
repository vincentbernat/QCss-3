from nevow import rend, tags as T, loaders

from qcss3.web.meta.past import MetaPastResource

class MetaApiResource(rend.Page):
    """
    API for metaweb.

    This API is similar to the standard one but will query several
    regular web services to build the answer.
    """

    addSlash = True
    docFactory = loaders.stan(T.html [ T.body [ T.p [ "Nothing here" ] ] ])

    def __init__(self, config):
        self.config = config
        rend.Page.__init__(self)

    def child_past(self, ctx):
        # We should check if we already have a date, but it is not really useful here
        return MetaPastResource(self)
