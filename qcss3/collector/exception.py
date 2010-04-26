"""
Exceptions for collector service
"""

class CollectorException(RuntimeError):
    pass

class NoPlugin(CollectorException):
    pass

class UnknownLoadBalancer(CollectorException):
    pass
