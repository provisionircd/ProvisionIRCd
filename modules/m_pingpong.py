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
    try:
        if type(self).__name__ == 'Server':
            #source = self
            if len(recv) == 2:
                #print('This should never happen')
                dest = list(filter(lambda s: s.sid == recv[1][1:] or s.hostname ==recv[1][1:], localServer.servers))[0].hostname
                data = ':{} PONG {}'.format(localServer.sid,dest.hostname)
                self._send(data)
                return

            dest = list(filter(lambda s: s.sid == recv[3] or s.hostname == recv[3], localServer.servers))
            if not dest:
                dest = localServer
            else:
                dest = dest[0]

            if self not in dest.replyPing:
                ### dest.eos will NOT work! So stop trying.
                _print('Server {} is not done syncing to {} yet, not replying to PING...'.format(dest.hostname, self.hostname), server=localServer)
                #if self not in localServer.syncDone:
                    #werequest = False if self not in localServer.linkrequester else True # ???
                    #_print('syncData() called from PING command... but why?', server=localServer)
                    #syncData(localServer, self, serverIntroducer=None, selfRequest=False)
                return

            data = ':{} PONG {} {}'.format(dest.sid, dest.hostname,recv[2])
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
        #print('PONG received for {}, ping reset.'.format(recv[0][1:]))
        source = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], localServer.servers))[0]
        source.ping = int(time.time())
