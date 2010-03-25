try:
    from twisted.application.service import IServiceMaker
except ImportError:
    pass
else:
    from zope.interface import implements
    from twisted.python import usage
    from twisted.plugin import IPlugin
    from qcss3.core import service

    class Options(usage.Options):
        synopsis = "[options]"
        longdesc = "Make a QCss3 server."
        optParameters = [
            ['config', 'c', '/etc/qcss3/qcss3.cfg'],
            ['port', 'p', 8089],
            ['interface', 'i', '127.0.0.1'],
            ]

    class QCssServiceMaker(object):
        implements(IServiceMaker, IPlugin)

        tapname = "qcss3"
        description = "QCss3 server."
        options = Options

        def makeService(self, config):
            return service.makeService(config)

    qcssServer = QCssServiceMaker()
