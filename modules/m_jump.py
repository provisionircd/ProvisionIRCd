#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/jump command
"""

import ircd

@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('jump')
@ircd.Modules.commands('jump')
def jump(self, localServer, recv):
    if type(self).__name__ == 'Server':
        source = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
        sourceServer = self
        recv = recv[1:]
    else:
        source = self
        sourceServer = self.server

    target = list(filter(lambda c: c.nickname.lower() == recv[1].lower() or c.uid.lower() == recv[1].lower(), localServer.users))
    if not target:
        self.sendraw(401, '{} :No such nick'.format(recv[1]))
        return
    target = target[0]
    validPort = False
    server = recv[2]
    if '.' not in server:
        self._send(':{} NOTICE {} :Invalid server "{}"'.format(localServer.hostname, source.uid,server))
        return
    port = recv[3]
    if '+' in port and port.startswith('+'):
        validPort = True
    if port.isdigit():
        port = int(port)
        validPort = True
        if port < 0 and port > 65535:
            validPort = False

    if not validPort:
        self._send(':{} NOTICE {} :Invalid port "{}"'.format(localServer.hostname, source.uid, port))
        return
    port = int(port)
    reason = 'User has been redirected to another server ([{} {}])'.format(server, port)
    msg = '*** {} ({}@{}) used JUMP to attempt to redirect {} to {} {}'.format(source.nickname, source.ident, source.hostname, target.nickname, server, port)
    localServer.snotice('s', msg)
    #data = ':{} NOTICE {} :*** Notice -- You are being redirected to {}, so goodbye'.format(localServer.hostname, target.uid, server)
    #target._send(data)
    target.sendraw('010', '{} {}'.format(server,port))
    data = ':{} {}'.format(source.uid,' '.join(recv))
    localServer.new_sync(localServer, sourceServer, data)
