#!/usr/bin/env python
# -*- coding: utf-8 -*-
from ircd import boot
import os
import sys
import time
import socket

def cmd_RESTART(self, localServer, recv):
    try:
        if len(recv) < 2:
            self.sendraw(461, ':RESTART Not enough parameters')
            return
        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return
        if not self.ocheck('o', 'restart'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return

        reason = 'Restart command received by {} ({}@{})'.format(self.nickname, self.ident, self.hostname)
        msg = '*** {}'.format(reason)
        localServer.snotice('s', msg)

        for user in [user for user in localServer.users if user.server == localServer]:
            user.quit(reason=None)
        for server in list(localServer.servers):
            server._send(':{} SQUIT {} :{}'.format(localServer.hostname, localServer.hostname, reason))

        localServer.running = False
        try:
            localServer.shutdown(socket.SHUT_RDWR)
        except:
            localServer.close()
        for s in localServer.listenSocks:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except:
                s.close()

        time.sleep(1)
        boot(conffile=localServer.conffile)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        #print(e)