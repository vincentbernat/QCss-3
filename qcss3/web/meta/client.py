import time
import urllib
import os

from twisted.internet import defer, task, reactor
from twisted.python import log
from twisted.web import client as twclient
from twisted.web.http_headers import Headers

from nevow import json

class ClientError(Exception):
    pass

class ClientNotJson(ClientError):
    """
    Service returned not JSon data
    """
    def __init__(self, data, status, headers):
        self.data = data
        self.status = status
        self.headers = headers

    def __str__(self):
        if "content-type" not in self.headers:
            return "Server returned not JSON data with code %s" % self.status
        return "Server returned %s instead of JSON with code %s" % (
            self.headers['content-type'].split(";")[1],
            self.status)

class MetaClient(object):
    """
    Client to query several web service at once.

    This client maintains a binding between load balancers and web
    services managing them. Given a load balancer, the client know
    which web service it should query and is able to failover another
    web service in case the first one fails.

    The client is also able to report the load balancers that he is
    able to handle.
    """

    def __init__(self, config):
        self.services = config.get('proxy', [])
        self.timeout = config.get('timeout', 2)    # Timeout for requests that should happen fast
        self.parallel = config.get('parallel', 10) # Number of parallel requests allowed
        self.expire = config.get('expire', 30)     # The list of load balancers expire
                                                   # after X seconds

        self.loadbalancers = {} # Mapping between load balancers and services
        self.updated = 0        # Last time updated
        self.refreshing = None

    def get(self, service, timeout, *requests):
        """
        Request a page from a remote service.

        @param service: URL of remote service to use
        @param timeout: timeout to use (0 to disable)
        @param request: request to issue (without prefix /api/1.0/ and without suffix /)
        @return: a tuple containing the deserialized data and the status code

        In case the data received is not JSon, the data is returned as an exception.
        """

        def process(data, status, headers):
            if "content-type" in headers and \
                    headers["content-type"][0].startswith("application/json;"):
                d = json.parse(data)
                return (d, status)
            raise ClientNotJson(data, status, headers)

        fact = twclient._makeGetterFactory(
            '%s/api/1.0/%s/' % (service,
                                "/".join([urllib.quote(r, '') for r in requests])),
            twclient.HTTPClientFactory,
            timeout=self.timeout,
            agent='QCss3 MetaWeb client on %s' % os.uname()[1])

        fact.deferred.addCallback(lambda data: process(data,
                                                       fact.status,
                                                       fact.response_headers))
        return fact.deferred

    def refresh(self):
        """
        Refresh (if needed) the list of handled load balancers.

        If a list of load balancers is already available, just trigger
        the refresh and return immediatly. We return a deferred only
        if the list is not available or is too old.

        This list is a mapping from load balancers to a list of
        servers that can handle this load balancer.
        """

        def add(service, data):
            if not data:
                return
            lbs, status = data
            if status != "200":
                log.msg("service %s responded error %s" % (service, status))
                return
            for lb in lbs:
                if lb in self.newloadbalancers:
                    self.newloadbalancers[lb].append(service)
                else:
                    self.newloadbalancers[lb] = [service]
            self.updated = time.time()

        def doWork(services):
            for service in services:
                d = self.get(service, self.timeout, "loadbalancer")
                d.addErrback(lambda x, service:
                                 log.msg("service %s is unavailable (%s)" % (service,
                                                                             x.value)),
                             service)
                d.addCallback(lambda x, service: add(service, x), service)
                yield d

        def finish():
            self.loadbalancers = self.newloadbalancers
            self.refreshing = None

        # Do we need to update?
        if self.refreshing:
            if self.loadbalancers:
                return
            return self.refreshing
        if time.time() - self.updated < self.expire:
            return

        # Start update
        self.newloadbalancers = {}
        dl = []
        coop = task.Cooperator()
        work = doWork(self.services)
        for i in xrange(self.parallel):
            d = coop.coiterate(work)
            dl.append(d)
        self.refreshing = defer.DeferredList(dl)
        self.refreshing.addBoth(lambda x: finish())
        if not self.loadbalancers:
            log.msg("No load balancer list available. Wait to get one.")
            return self.refreshing

    def get_loadbalancers(self):
        """
        Return a fresh list of load balancers that we are able to handle.
        """
        d = defer.maybeDeferred(self.refresh)
        d.addCallback(lambda x: self.loadbalancers.keys())
        return d

