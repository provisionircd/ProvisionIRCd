#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/squit command (server)
"""

import ircd

@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('squit')
@ircd.Modules.commands('squit')
def squit(self, localServer, recv):
    if type(self).__name__ == 'Server':
        source = [s for s in localServer.servers if s.sid == recv[0][1:]]
        if not source:
            return
        source = source[0]
        server = list(filter(lambda s: (s.sid and s.hostname) and (s.sid.lower() == recv[2].lower() or s.hostname.lower() == recv[2].lower()) and s != localServer, localServer.servers))
        if not server and server != localServer:
            return
        server = server[0]
        for s in [server for server in localServer.servers if server.hostname != recv[0][1:] and server.hostname != recv[2]]:
            if s.hostname == recv[2] or s.hostname == recv[0][1:]:
                continue
            # Notifying additional servers of netsplit.
            try:
                s._send(' '.join(recv))
            except:
                pass
        print('Issuing squit with source {}'.format(source))
        server.quit(' '.join(recv[3:]), noSquit=True, source=source)
        return

    if len(recv) > 2:
        reason = '[{}] {}'.format(self.nickname,' '.join(recv[2:]))
    else:
        reason = '[{}] no reason'.format(self.nickname)

    name = recv[1]

    if name.lower() in localServer.pendingLinks:
        localServer.pendingLinks.remove(name.lower())
    server = list(filter(lambda s: s.hostname.lower() == name.lower(), localServer.servers))
    if server:
        server = server[0]

    if not [server for server in localServer.servers if server.hostname == name]:
        localServer.notice(self, '*** Currently not connected to {}'.format(name))
        return

    msg = '*** {} ({}@{}) used SQUIT command for {}: {}'.format(self.nickname, self.ident, self.hostname, server.hostname, reason)
    localServer.snotice('s', msg)

    server.quit(reason)
