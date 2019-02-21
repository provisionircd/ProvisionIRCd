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

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('protoctl')
def protoctl(self, localServer, recv):
    if not hasattr(self, 'protoctl'):
        self.protoctl = []
    try:
        for p in [p for p in recv[1:] if p not in self.protoctl]:
            try:
                cap = p.split('=')[0]
                param = None
                self.protoctl.append(cap)
                if '=' in p:
                    param = p.split('=')[1]
                if cap == 'EAUTH':
                    self.hostname = param.split(',')[0]
                    _print('Hostname set from EAUTH: {}'.format(self.hostname), server=localServer)
                elif cap == 'SID':
                    for server in [server for server in localServer.servers if server.sid == param and server != self]:
                        self._send(':{} ERROR :SID {} is already in use on that network'.format(localServer.sid, param))
                        self.quit('SID {} is already in use on that network'.format(param))
                        return
                    self.sid = param
                elif cap == 'CHANMODES':
                    remote_modes = param.split(',')
                    local_modes = localServer.chmodes_string.split(',')
                    missing_modes = []
                    for n in localServer.channel_modes:
                        for m in [m for m in remote_modes[n] if m not in local_modes[n]]:
                            missing_modes.append(m)
                            ### Deny link because mismatched modes.
                    if missing_modes:
                        self._send(':{} ERROR :they are missing channel modes: {}'.format(self.sid, ', '.join(missing_modes)))
                        self.quit('we are missing channel modes: {}'.format(', '.join(missing_modes)))
                        return

            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
                _print(e, server=localServer)

            _print('{}Added PROTOCTL support for {} for server {}{}'.format(P, p, self, W), server=localServer)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
        _print(e, server=localServer)
