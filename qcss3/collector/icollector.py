"""
Interfaces for collectors
"""

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

    def execute(action, actionargs=None, vs=None, rs=None):
        """
        Execute an action

        @param action: action to execute.
        @param actionargs: optional arguments for the action; those
            arguments may be just ignored
        @param vs: if specified, execute action for this virtual server
        @param rs: if specified, execute action for this real server

        @return: C{None} if the action did not exist or the result of
           the action (which cannot be C{None}). Triggering an
           exception is a valid way to show that the action wasn't
           executed correctly.
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
