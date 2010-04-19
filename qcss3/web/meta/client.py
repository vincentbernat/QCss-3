import time
import urllib
import os
import copy

from twisted.internet import defer, task, reactor
from twisted.python import log
from twisted.web import client as twclient

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
    def handleStatus_502(self):
        self.failed = 1
    def handleStatus_503(self):
        self.failed = 1
    def handleStatus_504(self):
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

        def getPage(url):
            # Small reimplementation of twisted.web.client.getPage
            scheme, host, port, path = twclient._parse(url)
            factory = MetaHTTPClientFactory(url, timeout=self.timeout,
                                            agent='QCss3 MetaWeb client on %s' % os.uname()[1])
            if scheme == 'https':
                from twisted.internet import ssl
                contextFactory = ssl.ClientContextFactory()
                reactor.connectSSL(host, port, factory, contextFactory, timeout=self.timeout)
            else:
                reactor.connectTCP(host, port, factory, timeout=self.timeout)
            factory.deferred.addCallback(lambda data:
                                             (data, int(factory.status),
                                              "".join(factory.response_headers["content-type"])))
            return factory.deferred

        if date is not None:
            requests = ["past", date] + list(requests)
        url = '%s/api/1.0/%s/' % (service,
                                  "/".join([urllib.quote(r, '') for r in requests]))
        return getPage(url)

    def get_all(self, date, *requests):
        """
        Request a page from all remote services. In parallel. JSON only.

        We try to be clever: we just want to cover all load
        balancers. Therefore, we take the set of the first remote
        service for each load balancer and we query this set. If
        something fails, we can add another remote service to this
        set.

        @param date: if not C{None}, try in the past
        @param requests: request to issue
        @return: list of data
        """

        def process(x, service):
            data, status, content = x
            if status != 200:
                log.msg(
                    "got status code %d when querying service %s for request %r" %
                    (status, service, requests))
                return
            if not content.startswith("application/json;"):
                log.msg("got content type %r when querying service %s for request %r" %
                        (content, service, requests))
                return
            results.append(json.parse(data))

        def doWork():
            lbs = copy.deepcopy(self.loadbalancers[date])
            # Iterate on the list of services we need to query
            services = []       # list of currently running services
            failedservices = [] # list of failed services
            schedule(lbs, services, failedservices)
            for service in services[:]:
                d = queryService(service, services, failedservices, lbs)
                yield d

        def queryService(service, services, failedservices, lbs):
            d = self.get(service, 0, date, *requests)
            d.addCallbacks(lambda x, service: process(x, service),
                           lambda x, service: reschedule(service,
                                                         services, failedservices,
                                                         lbs),
                           callbackArgs=(service,),
                           errbackArgs=(service,))
            return d

        def schedule(lbs, services, failedservices):
            """
            Schedula additional services to cover the list of lbs.

            @param lbs: list of load balancer to cover
               (as a mapping lb->service)
            @param services: services already scheduled (will be
               modified by additional services to be queried)
            @param failedservices: services that should not be scheduled
            @return: list of new services to schedule
            """
            newservices = []
            # For each LB, check if it is currently covered
            for lb in lbs:
                found = False
                for service in services:
                    if service in lbs[lb]:
                        found = True
                if not found:
                    # This LB is not covered, try to add the first non
                    # failed service to our list of services to query.
                    for service in lbs[lb]:
                        if service not in failedservices:
                            services.append(service)
                            newservices.append(service)
                            break
                    # Here, we have a load balancer not covered
                    # anymore, maybe we should raise an exception.
                    log.msg("No service available for load balancer %r" % lb)
            return newservices

        def reschedule(service, services, failedservices, lbs):
            # Reschedule a failed service
            if service not in services:
                # The service is already removed, no worry but emit a warning
                log.msg("Service %r failed, cannot reschedule" % service)
                return
            # Remove all occurences of the failed service
            while True:
                try:
                    services.remove(service)
                except ValueError:
                    break
            failedservices.append(service)
            # Try a new service to replace it
            newservices = schedule(lbs, services, failedservices)
            newservices = [queryService(s, services, failedservices, lbs)
                           for s in newservices]
            if newservices:
                log.msg("Reschedule %r to other available services" % service)
            else:
                log.msg("Unable to reschedule %r, no other services available" %
                        service)
            return defer.DeferredList(newservices)

        def query():
            dl = []
            coop = task.Cooperator()
            work = doWork()
            for i in xrange(self.parallel):
                d = coop.coiterate(work)
                dl.append(d)
            return defer.DeferredList(dl)

        results = []
        d = defer.maybeDeferred(self.refresh, date)
        d.addCallback(lambda x: query())
        d.addCallback(lambda x: results)
        return d

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
