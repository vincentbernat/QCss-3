"""
Qcss3 service (as a TAC file)

This module should only be used with Twisted < 2.5
"""

from twisted.application import service
from qcss3.core import service as ws

application = service.Application('qcss3')
ws.makeService({"config": "/etc/qcss3/qcss3.cfg"}).setServiceParent(
    service.IServiceCollection(application))
