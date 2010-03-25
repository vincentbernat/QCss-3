# When modifying this class, also update doc/database.sql

from twisted.python import log
from twisted.internet import reactor, defer
from twisted.enterprise import adbapi

class Database:
    
    def __init__(self, config):
        p = adbapi.ConnectionPool("psycopg2",
                                  "host=%s port=%d dbname=%s "
                                  "user=%s password=%s" % (
                config.get('host', 'localhost'),
                config.get('port', 5432),
                config.get('database', 'qcss3'),
                config.get('username', 'qcss3'),
                config.get('password', 'qcss3')))
        self.pool = p
        reactor.callLater(0, self.checkDatabase)

    def checkDatabase(self):
        """
        Check if the database is running. Otherwise, stop the reactor.

        If the database is running, launch upgrade process.
        """
        d = self.pool.runOperation("SELECT 1 FROM loadbalancer LIMIT 1")
        d.addCallbacks(lambda _: self.upgradeDatabase(),
                       self.databaseFailure)
        return d

    def upgradeDatabase(self):
        """
        Try to upgrade database by running various upgrade_* functions.

        Those functions should be run as sooner as possible. However,
        to keep the pattern simple, we don't make them exclusive: the
        application can run while the upgrade is in progress.
        """
        fs = [x for x in dir(self) if x.startswith("upgradeDatabase_")]
        fs.sort()
        d = defer.succeed(None)
        for f in fs:
            d.addCallback(lambda x,ff: log.msg("Upgrade database: %s" %
                                            getattr(self, ff).__doc__), f)
            d.addCallback(lambda x,ff: getattr(self, ff)(), f)
        d.addCallbacks(
            lambda x: log.msg("database upgrade completed"),
            self.upgradeFailure)
        return d

    def databaseFailure(self, fail):
        """Unable to connect to the database"""
        log.msg("unable to connect to database:\n%s" % str(fail))
        reactor.stop()

    def upgradeFailure(self, fail):
        """When upgrade fails, just stop the reactor..."""
        log.msg("unable to update database:\n%s" % str(fail))
        reactor.stop()

#    def upgradeDatabase_01(self):
#        """First upgrade function"""
