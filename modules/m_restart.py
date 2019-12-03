#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/die command
"""

import ircd
import time

from handle.handleModules import UnloadModule

@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('restart')
@ircd.Modules.commands('restart')
def restart(self, localServer, recv):
    if recv[1] != localServer.conf['settings']['restartpass']:
        self.flood_penalty += 500000
        return self.sendraw(481, ':Permission denied')

    reason = 'Restart command received by {} ({}@{})'.format(self.nickname, self.ident, self.hostname)
    msg = '*** {}'.format(reason)
    localServer.snotice('s', msg)

    for user in [user for user in localServer.users if user.server == localServer]:
        user.quit(reason=None)
    for server in list(localServer.servers):
        server._send(':{} SQUIT {} :{}'.format(localServer.hostname, localServer.hostname, reason))

    localServer.running = False

    for m in list(localServer.modules):
        name = m.__name__
        UnloadModule(localServer, name)

    localServer.commands = []
    localServer.modules = {}
    localServer.events = []
    localServer.user_modes = {}
    localServer.channel_modes = {}

    for s in localServer.listen_socks:
        try:
            s.shutdown(socket.SHUT_RDWR)
        except:
            s.close()

    time.sleep(1)
    S = ircd.Server(conffile=localServer.conffile, forked=localServer.forked)
    S.run()
