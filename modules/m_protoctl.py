#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/protoctl command (server)
"""

import ircd

from handle.functions import _print, update_support

import os
import sys
import time

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

def checkSid(self, localServer, sid):
    try:
        check = list(filter(lambda s: s.sid == sid, localServer.servers+[localServer]))
        if check:
            _print('{}NETWORK ERROR: SID {} already found on this network!{}'.format(R, sid, W), server=localServer)
            ip, port = self.socket.getsockname()
            msg = 'Error connecting to server {}[{}:{}]: SID {} is already in use by a server'.format(self.hostname, ip, port, sid)
            if self not in localServer.linkrequester:
                self._send('ERROR :{}'.format(msg))
            elif localServer.linkrequester[self]['user']:
                localServer.linkrequester[self]['user'].send('NOTICE','*** {}'.format(msg))
            _print('{}Quitting double SID server {}{}'.format(R, self, W), server=localServer)
            self.quit('SID {} is already in use by another server'.format(sid), silent=True)
            return
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
        _print(e, server=localServer)


@ircd.Modules.req_class('Server')
@ircd.Modules.commands('protoctl')
def protoctl(self, localServer, recv):
    if not hasattr(self, 'protoctl'):
        self.protoctl = []
    try:
        for p in [p for p in recv[2:] if p not in self.protoctl]:
            self.protoctl.append(p)
            _print('{}Added PROTOCTL support for {} for server {}{}'.format(P, p, self, W), server=localServer)
        self.nextSid = None
        sid = ' '.join(recv).split('SID=')[1].split(' ')[0]
        checkSid(self, localServer, sid)
        if not self.sid:
            self.sid = sid
        else:
            self.nextSid = sid
            _print('{}SID of next incoming server set: {}{}'.format(G, self.nextSid, W), server=localServer)

        ### Grabbing only the non-paramental modes of the remote server.
        remoteModes = ' '.join(recv).split('CHANMODES=')[1].split(',')[3].split()[0]
        for mode in remoteModes:
            if mode not in localServer.channel_modes[3]:
                _print('{}Adding support for channel mode \'{}\'{}'.format(P, mode, W), server=localServer)
                localServer.channel_modes[3][mode] = (7, None)
    except IndexError:
        pass
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
        _print(e, server=localServer)
