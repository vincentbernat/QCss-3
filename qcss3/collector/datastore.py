"""
Memory datastore for QCss3

This module defines interfaces and interface implementations to store
the different entities in memory. This is equivalent to
doc/database.sql. Those structures are then stored in database.py.
"""

from zope.interface import Interface, Attribute, implements

class ILoadBalancer(Interface):
    """Interface for object containing the complete description of a load balancer"""

    name = Attribute('Name of this equipment')
    kind = Attribute('Type of this equipment')
    description = Attribute('Description of this equipment')

    extra = Attribute('Extra attributes (as a mapping)')
    virtualservers = Attribute('Virtual servers for this equipment (as a mapping)')

class LoadBalancer:
    implements(ILoadBalancer)

    def __init__(self, name, kind, description):
        self.name = name
        self.kind = kind
        self.description = description
        self.extra = {}
        self.virtualservers = {}

class IVirtualServer(Interface):
    """Interface for object containing the description of a virtual server"""

    name = Attribute('Name of this virtual server')
    vip = Attribute('Spec (VIP + port for example) of this virtual server')
    protocol = Attribute('Protocol of this virtual server')
    mode = Attribute('Load balancing mode of this virtual server')

    extra = Attribute('Extra attributes (as a mapping)')
    realservers = Attribute("Real servers for this virtual server (as a mapping)")

class VirtualServer:
    implements(IVirtualServer)

    def __init__(self, name, vip, protocol, mode):
        self.name = name
        self.vip = vip
        self.protocol = protocol
        self.mode = mode
        self.extra = {}
        self.realservers = {}

class ISorryOrRealServer(Interface):
    """
    Interface for object containing the description of a sorry/real server.

    In the database, sorry servers and real servers are stored in the
    same place. Since they are different entities, we separate them in
    the datastore.

    A sorry server is not really a real server and a real server is
    not really a sorry server and therefore, but they look
    alike. Their interfaces share most of the information.
    """

    name = Attribute('Name of this real/sorry server')
    rip = Attribute('IP of this real/sorry server')
    rport = Attribute('Port of this real/sorry server')
    protocol = Attribute('Protocol of this real/sorry server')
    state = Attribute('State of this real/sorry server (unknown/up/down/disabled)')
    extra = Attribute('Extra attributes (as a mapping)')

class ISorryServer(ISorryOrRealServer):
    """
    Interface for object containing the description of a sorry server.
    """

class IRealServer(ISorryOrRealServer):
    """
    Interface for object containing the description of a real server.
    """

    weight = Attribute('Weight of this real server')

class SorryServer:
    implements(ISorryServer)

    def __init__(self, name, rip, rport, protocol, state):
        self.name = name
        self.rip = rip
        self.rport = rport
        self.protocol = protocol
        self.state = state
        self.extra = {}

class RealServer:
    implements(IRealServer)

    def __init__(self, name, rip, rport, protocol, weight, state):
        self.name = name
        self.rip = rip
        self.rport = rport
        self.protocol = protocol
        self.weight = weight
        self.state = state
        self.extra = {}
