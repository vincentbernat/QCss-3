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

        # The following dict are all indexed by a date
        self.loadbalancers = {} # Mapping between load balancers and services
        self.newloadbalancers = {}
        self.updated = {}       # Last time updated
        self.refreshing = {}

    def get(self, service, timeout, date, *requests):
        """
        Request a page from a remote service.

        @param service: URL of remote service to use
        @param timeout: timeout to use (0 to disable)
        @param date: date of request (None if no date)
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

        if date is not None:
            requests = ["past", date] + list(requests)
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

    def refresh(self, date):
        """
        Refresh (if needed) the list of handled load balancers.

        If a list of load balancers is already available, just trigger
        the refresh and return immediatly. We return a deferred only
        if the list is not available or is too old.

        This list is a mapping from load balancers to a list of
        servers that can handle this load balancer.

        @param date: date to use for refresh
        """

        def add(service, date, data):
            if not data:
                return
            lbs, status = data
            if status != "200":
                log.msg("service %s responded error %s" % (service, status))
                return
            for lb in lbs:
                if lb in self.newloadbalancers[date]:
                    self.newloadbalancers[date][lb].append(service)
                else:
                    self.newloadbalancers[date][lb] = [service]
            self.updated[date] = time.time()

        def doWork(services, date):
            for service in services:
                d = self.get(service, self.timeout, date, "loadbalancer")
                d.addErrback(lambda x, service:
                                 log.msg("service %s is unavailable (%s)" % (service,
                                                                             x.value)),
                             service)
                d.addCallback(lambda x, service: add(service, date, x), service)
                yield d

        def finish():
            self.loadbalancers[date] = self.newloadbalancers[date]
            del self.refreshing[date]
            del self.newloadbalancers[date]
            # Expire some stuff
            t = time.time()
            delete = [d for d in self.updated
                      if d is not None and t - self.updated[d] > 4*self.expire]
            for d in delete:
                del self.updated[d]
                del self.loadbalancers[d]

        # Do we need to update?
        if date in self.refreshing:
            if date in self.loadbalancers:
                return
            return self.refreshing[date]
        if time.time() - self.updated.get(date, 0) < self.expire:
            return

        # Start update
        self.newloadbalancers[date] = {}
        dl = []
        coop = task.Cooperator()
        work = doWork(self.services, date)
        for i in xrange(self.parallel):
            d = coop.coiterate(work)
            dl.append(d)
        self.refreshing[date] = defer.DeferredList(dl)
        self.refreshing[date].addBoth(lambda x: finish())
        if not date in self.loadbalancers:
            log.msg("No load balancer list available. Wait to get one.")
            return self.refreshing[date]

    def get_loadbalancers(self, date):
        """
        Return a fresh list of load balancers that we are able to handle.

        @param date: date to use to retrieve load balancers
        """
        d = defer.maybeDeferred(self.refresh, date)
        d.addCallback(lambda x: self.loadbalancers[date].keys())
        return d

