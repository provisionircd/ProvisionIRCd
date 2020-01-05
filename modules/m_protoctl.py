#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/protoctl command (server)
"""

import ircd

from handle.functions import logging, update_support

W  = '\033[0m'  # white (normal)
P  = '\033[35m' # purple

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('protoctl')
def protoctl(self, localServer, recv):
    if not hasattr(self, 'protoctl'):
        self.protoctl = []
    try:
        for p in [p for p in recv[2:] if p not in self.protoctl]:
            try:
                cap = p.split('=')[0]
                param = None
                self.protoctl.append(cap)
                if '=' in p:
                    param = p.split('=')[1]
                if cap == 'EAUTH' and param:
                    self.hostname = param.split(',')[0]
                    logging.info('Hostname set from EAUTH: {}'.format(self.hostname))
                elif cap == 'SID' and param:
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
                    if missing_modes:
                        self._send(':{} ERROR :they are missing channel modes: {}'.format(self.sid, ', '.join(missing_modes)))
                        self.quit('we are missing channel modes: {}'.format(', '.join(missing_modes)))
                        return
                elif cap == 'EXTBAN':
                    remote_prefix = param[0]
                    remote_ban_types = param.split(',')[1]
                    local_prefix = None
                    if 'EXTBAN' in localServer.support:
                        local_prefix = localServer.support['EXTBAN'][0]
                    if remote_prefix != local_prefix:
                        self._send(':{} ERROR :extban prefixes are not the same. We have: {} but they have: {}'.format(self.sid, remote_prefix, local_prefix))
                        self.quit('extban prefixes are not the same. We have: {} but they have: {}'.format(local_prefix, remote_prefix))
                        return
                    local_ban_types = localServer.support['EXTBAN'][1:]
                    logging.info('We have bantypes: {}'.format(local_ban_types))
                    missing_ext_types = []
                    for m in [m for m in remote_ban_types if m not in local_ban_types]:
                        missing_ext_types.append(m)
                    if missing_ext_types:
                        self._send(':{} ERROR :they are missing ext bans: {}'.format(self.sid, ', '.join(missing_ext_types)))
                        self.quit('we are missing ext bans: {}'.format(', '.join(missing_ext_types)))
                        return

            except Exception as ex:
                logging.exception(ex)
                self.quit(ex)

            logging.info('{}Added PROTOCTL support for {} for server {}{}'.format(P, p, self, W))

    except Exception as ex:
        logging.exception(ex)
