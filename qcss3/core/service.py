import os
import sys
import yaml
import errno

from twisted.application import service, internet
from twisted.internet import reactor
from twisted.python import log
from nevow import appserver

from qcss3.core.database import Database
from qcss3.collector.service import CollectorService
from qcss3.web.site import MainPage

def makeService(config):
    configfile = yaml.load(file(config['config'], 'rb').read())
    application = service.MultiService()

    # database
    dbpool = None
    dbconfig = configfile.get('database', {})
    if dbconfig.get('enabled', True):
        dbpool = Database(dbconfig).pool

    # collector
    collector = None
    if dbpool is not None:
        collconfig = configfile.get('collector', {})
        if collconfig.get('enabled', True):
            collector = CollectorService(collconfig, dbpool)
            collector.setServiceParent(application)

    # web service
    web = None
    if dbpool is not None and collector is not None:
        webconfig = configfile.get('web', {})
        if webconfig.get('enabled', True):
            web = internet.TCPServer(webconfig.get('port', 8089),
                                     appserver.NevowSite(MainPage(webconfig,
                                                                  dbpool,
                                                                  collector)),
                                     interface=webconfig.get('interface', '127.0.0.1'))
            web.setServiceParent(application)

    if dbpool is None:
        reactor.callLater(0, log.msg, "Database has been disabled.")
    if collector is None:
        reactor.callLater(0, log.msg, "Collector has been disabled.")
    if web is None:
        reactor.callLater(0, log.msg, "Web service has been disabled.")

    return application
