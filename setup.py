import sys
import twisted
from distutils.core import setup, Extension
from qcss3 import VERSION

if __name__ == "__main__":
    setup(name="qcss3",
          version=VERSION,
          classifiers = [
            'Development Status :: 4 - Beta',
            'Environment :: No Input/Output (Daemon)',
            'Environment :: Web Environment',
            'Framework :: Twisted',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: GNU General Public License (GPL)',
            'Operating System :: POSIX',
            'Programming Language :: Python',
            'Topic :: System :: Networking',
            ],
          url='https://trac.luffy.cx/qcss3/',
          description='generic web interface for load balancers',
          author='Vincent Bernat',
          author_email="bernat@luffy.cx",
          ext_modules= [
            Extension('qcss3.collector.snmp',
                      libraries = ['netsnmp', 'crypto'],
                      sources= ['qcss3/collector/snmp.c']),
            ],
          packages=["qcss3",
                    "qcss3.collector",
                    "qcss3.collector.loadbalancer",
                    "qcss3.core",
                    "qcss3.web",
                    "twisted.plugins"],
          package_data={'twisted': ['plugins/qcss3_plugin.py']}
          )
