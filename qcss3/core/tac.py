from twisted.application import service
from qcss3.core import service as ws

application = service.Application('qcss3')
ws.makeService({"config": "/etc/qcss3/qcss3.cfg",
                "interface": '127.0.0.1',
                "port": 8089}).setServiceParent(
    service.IServiceCollection(application))
