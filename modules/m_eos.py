#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/eos command (server)
"""

import ircd

from handle.functions import _print

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('eos')
def eos(self, localServer, recv):
    source = list(filter(lambda s: s.sid == recv[0][1:], localServer.servers))
    if not source:
        return
    source = source[0]
    if source.eos:
        _print('INFO: remote server sent EOS twice!', server=localServer)
        return
    raw = ' '.join(recv)
    localServer.new_sync(localServer, self, raw)
    #localServer.syncToServers(localServer, self, raw)
    _print('{}EOS received by: {}{}'.format(Y, source.hostname, W), server=localServer)
    for s in [s for s in localServer.servers if s.introducedBy == source]:
        _print('Also setting EOS for {} to be true'.format(s), server=localServer)
        s.eos = True

    localServer.replyPing[source] = True
    _print('Server {} will now reply to PING requests from {} (EOS)'.format(localServer.hostname, source.hostname), server=localServer)
    for server in [server for server in localServer.servers if server != source and server.socket and source.uplink != server]:
        _print('Sending PONG from {} to {}'.format(source.hostname, server.hostname), server=localServer)
        server._send(':{} PONG {}'.format(source.sid, server.hostname))
        for s in [s for s in localServer.servers if s.introducedBy == server and s.uplink != server]:
            _print('Sending2 PONG from {} to {}'.format(s.hostname, server.hostname), server=localServer)
            server._send(':{} PONG {}'.format(s.sid, server.hostname))

    if source.hostname.lower() in localServer.pendingLinks:
        localServer.pendingLinks.remove(source.hostname.lower())
    #if not source.eos:
    #    _print('{}Remote server {} is done syncing! My turn...{}'.format(Y, self.hostname, W), server=localServer)
    #    syncData(localServer, self, serverIntroducer=None, selfRequest=False)
    source.eos = True
