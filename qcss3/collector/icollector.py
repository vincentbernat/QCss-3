from zope.interface import Interface, Attribute

class ICollector(Interface):
    """Interface for a collector gathering load balancer information"""

    oids = Attribute("OID mapping to be used when collecting")

    def collect(vs=None, rs=None):
        """
        Collect data for the whole load balancer or a subset of it

        @param vs: if specified, collect only the given virtual server
        @param rs: if specified, collect only the given real server
        @return: an object implementing C{ILoadBalancer},
            C{IVirtualServer}, C{IRealServer} or C{ISorryServer}.
        """

    def actions(vs=None, rs=None):
        """
        Indicate which actions are possible.

        @param vs: if specified, return actions possible for this virtual server
        @param rs: if specified, return actions possible for this real server
        @return: a mapping between possible actions and their description
        """

class ICollectorFactory(Interface):
    """
    Interface for a factory of collector gathering load balancer information.

    This interface is responsible to provide an object implementing
    C{ICollector} interface for the load balancer.
    """

    def canBuildCollector(proxy, description, oid):
        """
        Does this factory can build a collector for the equipement given as a proxy?

        @param proxy: proxy to use to determine if this factory is appropriate
        @param description: sysDescr from the equipment
        @param oid: sysObjectOID from the equipment
        @return: C{True} if we can build a collector / may be deferred
        """

    def buildCollector(config, proxy, name, description):
        """
        Build a collector for the given equipment as a proxy

        @param config: configuration elements
        @param proxy: proxy to use to access loadbalancer
        @param name: name of the load balancer
        @param description: sysDescr from the equipment
        @return: an instance implementing C{ICollector}
        """
