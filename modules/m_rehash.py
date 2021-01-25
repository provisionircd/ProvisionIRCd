"""
/rehash command
"""

import gc

import ircd

gc.enable()
from handle.handleConf import checkConf


@ircd.Modules.command
class Rehash(ircd.Command):
    """
    Reloads the configuration files in memory.
    """

    def __init__(self):
        self.command = 'rehash'
        self.req_flags = 'rehash'

    def execute(self, client, recv):
        msg = '*** {} ({}@{}) is rehashing the server configuration file...'.format(client.nickname, client.ident, client.hostname, local=True)
        self.ircd.snotice('s', msg)

        if True:
            ### Need to add some param shit, now too lazy and hot.
            self.ircd.dnsblCache = {}
            self.ircd.throttle = {}
            self.ircd.hostcache = {}

        checkConf(self.ircd, client, self.ircd.confdir, self.ircd.conffile, rehash=True)

        gc.collect()
        del gc.garbage[:]
