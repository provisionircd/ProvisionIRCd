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
        _print('ERROR: could not find server for {}'.format(recv[0][1:]), server=localServer)
        return
    source = source[0]
    if source.eos:
        _print('ERROR: remote server sent EOS twice!', server=localServer)
        return
    localServer.new_sync(localServer, self, ' '.join(recv))
    _print('{}EOS received by: {}{}'.format(Y, source.hostname, W), server=localServer)
    for s in [s for s in localServer.servers if s.introducedBy == source]:
        _print('Also setting EOS for {} to be true'.format(s), server=localServer)
        s.eos = True
    if source.hostname.lower() in localServer.pendingLinks:
        localServer.pendingLinks.remove(source.hostname.lower())
    source.eos = True
    if source in localServer.sync_queue:
        for e in localServer.sync_queue[source]:
            _print('Sending queued data to {}: {}'.format(source, e), server=localServer)
            localServer.new_sync(localServer, source, e)
        del localServer.sync_queue[source]
