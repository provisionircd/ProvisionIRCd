#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

import handle.handleLogs as Logger

def _print(txt):
    Logger.write(txt)
    #print(txt)

def cmd_SQUIT(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            ### Do stuff here.
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
            server.quit(' '.join(recv[3:]), noSquit=True)
            return

        if len(recv) < 2:
            self.sendraw(461, ':SQUIT Not enough parameters')
            return

        if len(recv) > 2:
            reason = '[{}] {}'.format(self.nickname,' '.join(recv[2:]))
        else:
            reason = '[{}] no reason'.format(self.nickname)

        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return

        if not self.ocheck('o', 'squit'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return

        name = recv[1]

        if name.lower() in localServer.pendingLinks:
            localServer.pendingLinks.remove(name.lower())
        server = list(filter(lambda s: s.hostname.lower() == name.lower(), localServer.servers))
        if server:
            server = server[0]

        if not [server for server in localServer.servers if server.hostname == name]:
            self.send('NOTICE', '*** Currently not connected to {}.'.format(name))
            return
        #source = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], localServer.servers))[0]

        msg = '*** {} ({}@{}) used SQUIT command for {}: {}'.format(self.nickname, self.ident, self.hostname, server.hostname, reason)
        localServer.snotice('s', msg)

        server.quit(reason)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e)
