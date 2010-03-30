import os
import sys
import yaml
import errno

from twisted.application import service, internet
from nevow import appserver

from qcss3.core.database import Database
from qcss3.collector.service import CollectorService
from qcss3.web.site import MainPage

def makeService(config):
    # configuration file
    configfile = yaml.load(file(config['config'], 'rb').read())
    # database
    dbpool = Database(configfile.get('database', {})).pool
    application = service.MultiService()
    # collector
    collector = CollectorService(configfile, dbpool)
    collector.setServiceParent(application)
    # web service
    web = internet.TCPServer(config['port'],
                             appserver.NevowSite(MainPage(configfile,
                                                          dbpool,
                                                          collector)),
                             interface=config['interface'])
    web.setServiceParent(application)

    return application
