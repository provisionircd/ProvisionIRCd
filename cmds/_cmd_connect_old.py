#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import sys
import os
import importlib
import time
from handle.handleLink import Link

def connectTo(self, localServer, name, autoLink=False):
    try:
        localServer.pendingLinks.append(name.lower())
        host, port = localServer.conf['link'][name]['outgoing']['host'], localServer.conf['link'][name]['outgoing']['port']
        if host in ['127.0.0.1', '0.0.0.0', 'localhost'] and (port in localServer.conf['listen'] and localServer.conf['listen'][str(port)]['options'] == 'servers'):
            return
        pswd = localServer.conf['link'][name]['pass']
        is_ssl = False
        try:
            if 'ssl' in localServer.conf['link'][name]['options']:
                is_ssl = True
        except:
            pass

        l = Link(self, localServer, name, host, port, pswd, is_ssl, autoLink)
        l.start()

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)
        if self:
            if name.lower() in localServer.pendingLinks:
                localServer.pendingLinks.remove(name.lower())
            self.send('NOTICE', '*** ERROR: {}'.format(e))

def cmd_CONNECT(self, localServer, recv):
    if len(recv) < 2:
        return self.sendraw(461, ':CONNECT Not enough parameters')
    if 'HTTP/' in recv:
        self.quit('Illegal command')
        return
    if 'o' not in self.modes:
        return self.sendraw(481, ':Permission denied - You are not an IRC Operator')
    if not self.ocheck('o', 'connect'):
        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
    name = recv[1]

    if name.lower() == localServer.hostname.lower():
        self.send('NOTICE', '*** Cannot link to own local server.')
        return

    if name not in localServer.conf['link']:
        self.send('NOTICE', '*** Server {} is not configured for linking.'.format(name))
        return
    server = list(filter(lambda s: s.hostname.lower() == name.lower(), localServer.servers))
    if server:
        server = server[0]
        if not server.eos and name.lower() in localServer.pendingLinks:
            self.send('NOTICE', '*** Link to {} is currently being processed.'.format(name))
            return

    if [server for server in set(localServer.servers) if server.hostname == name and server.eos]:
        self.send('NOTICE', '*** Already linked to {}.'.format(name))
        return

    connectTo(self, localServer, name)
