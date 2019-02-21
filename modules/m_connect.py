#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/connect command
"""

import ircd
import sys
import os
from handle.handleLink import Link
from handle.functions import _print

def connectTo(self, localServer, name, autoLink=False):
    try:
        host, port = localServer.conf['link'][name]['outgoing']['host'], localServer.conf['link'][name]['outgoing']['port']
        if host in ['127.0.0.1', '0.0.0.0', 'localhost'] and (port in localServer.conf['listen'] and localServer.conf['listen'][str(port)]['options'] == 'servers'):
            return
        pswd = localServer.conf['link'][name]['pass']
        is_ssl = False
        if 'options' in localServer.conf['link'][name] and 'ssl' in localServer.conf['link'][name]['options']:
            is_ssl = True
        l = Link(self, localServer, name, host, port, pswd, is_ssl, autoLink)
        l.start()

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
        if self:
            if name.lower() in localServer.pendingLinks:
                localServer.pendingLinks.remove(name.lower())
            self.send('NOTICE', '*** ERROR: {}'.format(e))


@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('connect')
@ircd.Modules.commands('connect')
def connect(self, localServer, recv):
    if 'HTTP/' in recv:
        self.quit('Illegal command')
        return
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
            return localServer.notice(self, '*** Link to {} is currently being processed.'.format(name))

    if [server for server in set(localServer.servers) if server.hostname == name and server.eos]:
        self.send('NOTICE', '*** Already linked to {}.'.format(name))
        return
    localServer.pendingLinks.append(name.lower())
    connectTo(self, localServer, name)
