"""
/gc command
"""

import ircd

import gc
#import objgraph

@ircd.Modules.req_modes('o')
@ircd.Modules.commands('gc')
def cmd_gc(self, localServer, recv):
    localServer.dnsblCache = {}
    localServer.throttle = {}
    localServer.hostcache = {}
    #for w in dict(localServer.whowas):
    #    del localServer.whowas[w]

    gc.collect()
    gc.get_objects()
    del gc.garbage[:]
