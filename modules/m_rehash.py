#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/rehash command
"""

import ircd

import gc
from handle.handleConf import checkConf

@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('rehash')
@ircd.Modules.commands('rehash')
def rehash(self, localServer, recv):
    msg = '*** {} ({}@{}) is rehashing the server configuration file...'.format(self.nickname, self.ident, self.hostname, local=True)
    localServer.snotice('s', msg)

    if True:
        ### Need to add some param shit, now too lazy and hot.
        localServer.dnsblCache = {}
        localServer.throttle = {}
        localServer.hostcache = {}

    checkConf(localServer, self, localServer.confdir, localServer.conffile, rehash=True)

    gc.collect()
    del gc.garbage[:]
