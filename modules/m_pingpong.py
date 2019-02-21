#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ping/pong handler
"""

import ircd

import os
import sys
import time

from handle.handleLink import syncData
from handle.functions import _print

@ircd.Modules.params(1)
@ircd.Modules.commands('ping')
def ping(self, localServer, recv):
    ### [':00B', 'PING', 'services.dev.provisionweb.org', 'dev.provisionweb.org']
    try:
        if type(self).__name__ == 'Server':
            dest = list(filter(lambda s: s.sid == recv[3] or s.hostname == recv[3], localServer.servers+[localServer]))
            if not dest:
                _print('Server {} requested a PING to unknown server {}'.format(self, recv[3]))
                return
            data = ':{} PONG {} {}'.format(dest[0].sid, dest[0].hostname, recv[2])
            self._send(data)

        else:
            self._send(':{} PONG {} :{}'.format(localServer.hostname, localServer.hostname, recv[1]))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname,exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

@ircd.Modules.params(1)
@ircd.Modules.commands('pong')
def pong(self, localServer, recv):
    if type(self).__name__ == 'Server':
        ### Sent: :00B PONG services.dev.provisionweb.org dev.provisionweb.org
        source = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], localServer.servers))[0]
        source.ping = int(time.time())
