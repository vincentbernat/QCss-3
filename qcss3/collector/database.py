"""
Database dumping of in-memory datastore for QCss3

This module writes to database the content of a memory datastore using
adapters. For example, if we want to write an object representing an a
load balancer (implementing C{ILoadBalancer} interface), we will use
C{IDatabaseWriter(lb).write(txn)} where C{lb} is the load balancer and
C{txn} a transaction to use.
"""

from zope.interface import Interface, implements
from twisted.python import components

from qcss3.collector.datastore import ILoadBalancer, IVirtualServer, IRealServer, ISorryServer

class IDatabaseWriter(Interface):
    """Interface to write an entity to the database"""

    def write(txn, id=None):
        """
        Dump the current entity to database using the given transaction.

        @param txn: transaction to use to dump to the database
        @param id: unique id to use for the entity (if needed)
        """

class LoadBalancerWriter:
    implements(IDatabaseWriter)

    def __init__(self, loadbalancer):
        self.loadbalancer = loadbalancer

    def write(self, txn, id=None):
        """Dump the loadbalancer to the database"""
        # Remove existing information
        txn.execute("UPDATE loadbalancer SET deleted=CURRENT_TIMESTAMP "
                    "WHERE name=%(name)s AND deleted='infinity'",
                    {'name': self.loadbalancer.name})
        # Insert new information
        txn.execute("INSERT INTO loadbalancer "
                    "(name, type, description) VALUES "
                    "(%(name)s, %(kind)s, %(description)s)",
                    { 'name': self.loadbalancer.name,
                      'kind': self.loadbalancer.kind,
                      'description': self.loadbalancer.description })
        # Then write virtual servers information
        virtualservers = self.loadbalancer.virtualservers
        for virtualserver in virtualservers:
            IDatabaseWriter(
                virtualservers[virtualserver]).write(txn,
                                                     (self.loadbalancer.name,
                                                      virtualserver))

class VirtualServerWriter:
    implements(IDatabaseWriter)

    def __init__(self, virtualserver):
        self.virtualserver = virtualserver

    def write(self, txn, id=None):
        """
        Dump the virtual server to the database.

        @param id: (name of loadbalancer, ID of the virtual server)
        """
        lb, vs = id
        # Remove existing information
        txn.execute("UPDATE virtualserver SET deleted=CURRENT_TIMESTAMP "
                    "WHERE lb=%(lb)s AND vs=%(vs)s AND deleted='infinity'",
                    {'lb': lb, 'vs': vs})
        # Insert new information
        txn.execute("INSERT INTO virtualserver "
                    "(lb, vs, name, vip, protocol, mode) VALUES "
                    "(%(lb)s, %(vs)s, %(name)s, %(vip)s, %(protocol)s, %(mode)s)",
                    {'lb': lb, 'vs': vs,
                     'name': self.virtualserver.name,
                     'vip': self.virtualserver.vip,
                     'protocol': self.virtualserver.protocol,
                     'mode': self.virtualserver.mode})
        # Insert extra information
        for key in self.virtualserver.extra:
            txn.execute("INSERT INTO virtualserver_extra "
                        "(lb, vs, key, value) VALUES "
                        "(%(lb)s, %(vs)s, %(key)s, %(value)s)",
                        { 'lb': lb, 'vs': vs, 'key': key,
                          'value': self.virtualserver.extra[key] })
        # Insert real servers
        realservers = self.virtualserver.realservers
        for realserver in realservers:
            IDatabaseWriter(
                realservers[realserver]).write(txn,
                                               (lb, vs, realserver))

class RealOrSorryServerWriter:
    implements(IDatabaseWriter)

    def __init__(self, realserver):
        self.realserver = realserver

    def write(self, txn, id=None):
        """
        Dump the real/sorry server to the database.

        @param id: (name of load balancer,
            ID of the virtualserver, ID of the real server)
        """
        lb, vs, rs = id
        # Remove existing information
        txn.execute("UPDATE realserver SET deleted=CURRENT_TIMESTAMP "
                    "WHERE lb=%(lb)s AND vs=%(vs)s AND rs=%(rs)s "
                    "AND deleted='infinity'",
                    {'lb': lb, 'vs': vs, 'rs': rs})
        # Insert new information
        weight = None
        if IRealServer.providedBy(self.realserver):
            weight = self.realserver.weight
        txn.execute("INSERT INTO realserver "
                    "(lb, vs, rs, name, rip, port, protocol, weight, rstate, sorry) "
                    "VALUES "
                    "(%(lb)s, %(vs)s, %(rs)s, %(name)s, %(rip)s, "
                    "%(port)s, %(protocol)s, %(weight)s, %(rstate)s, %(sorry)s)",
                    {'lb': lb, 'vs': vs, 'rs': rs,
                     'name': self.realserver.name,
                     'rip': self.realserver.rip,
                     'port': self.realserver.rport,
                     'protocol': self.realserver.protocol,
                     'weight':  weight,
                     'rstate': self.realserver.state,
                     'sorry': ISorryServer.providedBy(self.realserver) })
        # Insert extra information
        for key in self.realserver.extra:
            txn.execute("INSERT INTO realserver_extra VALUES "
                        "(%(lb)s, %(vs)s, %(rs)s, %(key)s, %(value)s)",
                        { 'lb': lb, 'vs': vs, 'rs': rs, 'key': key,
                          'value': self.realserver.extra[key] })

components.registerAdapter(
    LoadBalancerWriter,
    ILoadBalancer, 
    IDatabaseWriter)
components.registerAdapter(
    VirtualServerWriter,
    IVirtualServer, 
    IDatabaseWriter)
components.registerAdapter(
    RealOrSorryServerWriter,
    IRealServer, 
    IDatabaseWriter)
components.registerAdapter(
    RealOrSorryServerWriter,
    ISorryServer, 
    IDatabaseWriter)
