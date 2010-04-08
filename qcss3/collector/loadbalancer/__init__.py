"""
Collectors for load balancers.

Most modules make use of C{deferredGenerator} a feature from Twisted
to allow easier use of deferred. They don't use C{inlineCallbacks}
because this only works from Python 2.5.

A small documentation on C{deferredGenerator} is available here:
 U{http://twistedmatrix.com/documents/8.1.0/api/twisted.internet.defer.html#deferredGenerator}
"""
