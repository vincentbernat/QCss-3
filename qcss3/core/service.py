import os
import sys
import yaml
import errno

from twisted.application import service

from qcss3.core.database import Database
from qcss3.collector.service import CollectorService

def makeService(config):
    # configuration file
    configfile = yaml.load(file(config['config'], 'rb').read())
    # database
    dbpool = Database(configfile.get('database', {})).pool
    application = service.MultiService()

    collector = CollectorService(configfile, dbpool)
    collector.setServiceParent(application)

    return application
