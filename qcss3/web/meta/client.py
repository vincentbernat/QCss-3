import time
import urllib
import os

from twisted.internet import defer, task, reactor
from twisted.python import log
from twisted.web import client as twclient
from twisted.web.http_headers import Headers

from nevow import json, inevow, rend

from qcss3.web.timetravel import IPastDate

class ClientError(Exception):
    pass

class MetaHTTPPageGetter(twclient.HTTPPageGetter):
    """
    Page getter protocol.

    Unlike the original page getter, this one does not raise
    exceptions when getting values like 404. Exceptions are raisen on
    network errors (connect timeout, connection refused) or on error
    500.
    """
    def handleStatusDefault(self):
        pass
    def handleStatus_500(self):
        self.failed = 1
    def handleStatus_200(self):
        self.status = "200"

class MetaHTTPClientFactory(twclient.HTTPClientFactory):
    protocol = MetaHTTPPageGetter

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
        @return: a tuple containing the data, the status code and the content-type
        """
        if date is not None:
            requests = ["past", date] + list(requests)
        fact = twclient._makeGetterFactory(
            '%s/api/1.0/%s/' % (service,
                                "/".join([urllib.quote(r, '') for r in requests])),
            MetaHTTPClientFactory,
            timeout=self.timeout,
            agent='QCss3 MetaWeb client on %s' % os.uname()[1])

        fact.deferred.addCallback(lambda data: 
                                  (data, int(fact.status),
                                   "".join(fact.response_headers["content-type"])))
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
            lbs, status, content = data
            if status != 200:
                log.msg("service %s responded error %s" % (service, status))
                return
            if not content.startswith("application/json;"):
                log.msg("service %s did not answer with JSON (%s)" % content)
                return
            lbs = json.parse(lbs)
            for lb in lbs:
                if lb in self.newloadbalancers[date]:
                    self.newloadbalancers[date][lb].append(service)
                else:
                    self.newloadbalancers[date][lb] = [service]
            self.updated[date] = time.time()

        def doWork(services, date):
            for service in services:
                d = self.get(service, self.timeout, date, "loadbalancer")
                d.addCallbacks(lambda x, service: add(service, date, x),
                               lambda x, service:
                                   log.msg("service %s is unavailable (%s)" % (service,
                                                                               x.value)),
                               callbackArgs=(service,),
                               errbackArgs=(service,))
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


class ProxyResource(rend.Page):
    """
    Special resource acting like a proxy.
    """

    def __init__(self, lb, client):
        self.lb = lb
        self.client = client
        self.segments = ()
        rend.Page.__init__(self)

    def locateChild(self, ctx, segments):
        # Eeat all remaining segments
        self.segments = segments
        return self, ()

    def renderHTTP(self, ctx):
        """
        Proxy a request.

        The request (contained in ctx) is proxied using the service
        for lb.

        @param ctx: context of the request
        """

        def cycle(services=None):
            if services is None:
                if self.lb not in self.client.loadbalancers[date]:
                    return None
                services = self.client.loadbalancers[date][self.lb][:]
            if not services:
                return nogateway()

            d = defer.succeed(None)
            d.addCallback(lambda x: self.client.get(services[0], 0,
                                                    date, "loadbalancer",
                                                    self.lb, *segments))
            d.addCallbacks(lambda x: process(x, services[0]),
                           lambda x: error(x, services))
            return d

        def error(x, services):
            log.msg("while querying %s, get error %s" % (services[0], x.value))
            return cycle(services[1:])

        def process(x, service):
            # Copy verbatim
            data, status, content = x
            request.setResponseCode(int(status))
            request.setHeader("Content-Type", content)
            request.setHeader("X-QCss-Server", service)
            return data

        def nogateway(x):
            request.setResponseCode(504) # Gateway timeout
            return "No gateway available"

        try:
            date = ctx.locate(IPastDate)
        except KeyError:
            date = None
        request = inevow.IRequest(ctx)
        segments = [x for x in self.segments if x]
        d = defer.maybeDeferred(self.client.refresh, date)
        d.addCallback(lambda x: cycle())
        return d
