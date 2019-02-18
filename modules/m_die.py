#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/die command
"""

import ircd

from handle.functions import cloak

@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('die')
@ircd.Modules.commands('die')
def die(self, localServer, recv):
    if recv[1] != localServer.conf['settings']['diepass']:
        self.flood_penalty += 500000
        return self.sendraw(481, ':Permission denied')
    reason = 'Die command received by {} ({}@{})'.format(self.nickname,self.ident,self.hostname)
    msg = '*** {}'.format(reason)
    localServer.snotice('s', msg)
    for server in list(localServer.servers):
        server._send(':{} SQUIT {} :{}'.format(localServer.hostname,localServer.hostname,reason))

    for user in [user for user in localServer.users if user.server == localServer]:
        user.quit(reason=None)

    localServer.running = False

    for s in localServer.listen_socks:
        try:
            s.shutdown(socket.SHUT_WR)
        except:
            s.close()