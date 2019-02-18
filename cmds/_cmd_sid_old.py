#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time

from ircd import Server
from handle.functions import _print
from handle.handleLink import syncData

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
G = '\033[32m' # green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

def checkSid(self, localServer, sid, hostname):
    sid_exist = list(filter(lambda s: s.sid == sid, localServer.servers+[localServer]))
    hostname_exist = list(filter(lambda s: s.hostname == hostname, localServer.servers+[localServer]))
    if sid_exist or hostname_exist:
        _print('{}NETWORK ERROR: {} {} already found on this network!{}'.format(R, 'SID' if sid_exist else 'Hostname', sid if sid_exist else hostname, W), server=localServer)
        ip, port = self.socket.getsockname()
        msg = 'Error connecting to server {}[{}:{}]: {} {} is already in use by a server'.format(self.hostname, ip, port, 'SID' if sid_exist else 'Hostname', sid if sid_exist else hostname)
        if self not in localServer.linkrequester:
            self._send('ERROR :{}'.format(msg))
        elif localServer.linkrequester[self]['user']:
            localServer.linkrequester[self]['user'].send('NOTICE','*** {}'.format(msg))
        self.quit('{} {} is already in use by another server'.format('SID' if sid_exist else 'Hostname', sid if sid_exist else hostname), silent=True)
        return

def cmd_SID(self, localServer, recv):
    try:
        if type(self).__name__ != 'Server':
            return

        sid = recv[4]
        hostname = recv[2]
        checkSid(self, localServer, sid, hostname)

        hopcount = recv[3]

        if hostname == self.hostname:
            ### Own server?
            return

        from ircd import Server
        newServer = Server(origin=localServer,serverLink=True)

        newServer.hostname = hostname

        clearPreviousHopcounts = list(filter(lambda s: s.hopcount == hopcount, localServer.servers))
        for s in list(clearPreviousHopcounts):
            s.hopcount = None

        newServer.hopcount = hopcount
        newServer.name = recv[5][1:]

        newServer.introducedBy = self
        newServer.sid = sid
        _print('{}New server added to the network: {}{}'.format(G, newServer.hostname, W), server=localServer)
        _print('{}SID: {}{}'.format(G, newServer.sid, W), server=localServer)
        _print('{}Introduced by: {} ({}) {}'.format(G, self.hostname, self.sid, W), server=localServer)
        _print('{}Hopcount: {}{}'.format(G, newServer.hopcount, W), server=localServer)
        ### How many hops do I need to reach newServer? == hopcount

        syncData(localServer, newServer, self, selfRequest=False)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R,exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj,W)
        _print(e, server=localServer)
