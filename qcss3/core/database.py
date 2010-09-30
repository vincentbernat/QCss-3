"""
Database initialization and upgrade.
"""

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

    def upgradeDatabase_01(self):
        """add action table"""

        def create(txn):
            """Create action table and its indexes."""
            txn.execute("""
CREATE TABLE action (
  lb          text      NOT NULL,
  vs          text      NULL,
  rs          text      NULL,
  action      text      NOT NULL,
  label       text      NOT NULL,
  PRIMARY KEY (lb, vs, rs, action)
)""")
            txn.execute("CREATE INDEX action_lb_vs_rs ON action (lb, vs, rs)")

        d = self.pool.runOperation("SELECT 1 FROM action LIMIT 1")
        d.addCallbacks(lambda _: None,
                       lambda _: self.pool.runInteraction(create))
        return d

    def upgradeDatabase_02(self):
        """add past tables"""

        def addpast(txn):
            for table in ["loadbalancer", "virtualserver", "virtualserver_extra",
                          "realserver", "realserver_extra"]:
                txn.execute("CREATE TABLE %s_past (LIKE %s)" % ((table,)*2))
                # Create view
                txn.execute("CREATE VIEW %s_full AS "
                            "(SELECT * FROM %s UNION SELECT * FROM %s_past)" % ((table,)*3))
                # Add index on `deleted'
                txn.execute("CREATE INDEX %s_past_deleted ON %s_past (deleted)" % ((table,)*2))
            # Primary keys
            txn.execute("ALTER TABLE loadbalancer_past ADD PRIMARY KEY (name, deleted)")
            txn.execute("ALTER TABLE virtualserver_past ADD PRIMARY KEY (lb, vs, deleted)")
            txn.execute("ALTER TABLE virtualserver_extra_past ADD PRIMARY KEY (lb, vs, key, deleted)")
            txn.execute("ALTER TABLE realserver_past ADD PRIMARY KEY (lb, vs, rs, deleted)")
            txn.execute("ALTER TABLE realserver_extra_past ADD PRIMARY KEY (lb, vs, rs, key, deleted)")

        d = self.pool.runOperation("SELECT 1 FROM loadbalancer_past LIMIT 1")
        d.addCallbacks(lambda _: None,
                       lambda _: self.pool.runInteraction(addpast))
        return d
