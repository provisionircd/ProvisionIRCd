#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/server and /sid command (server)
"""

import ircd
import sys
import os
Server = ircd.Server

from handle.functions import match, _print
from handle.handleLink import syncData, selfIntroduction

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

@ircd.Modules.params(5)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('server')
def server(self, localServer, recv):
    try:
        exists = list(filter(lambda s: s.hostname.lower() == recv[2].lower(), localServer.servers+[localServer]))
        if exists:
            _print('Server {} already exists on this network2'.format(recv[2]), server=localServer)
            #self.quit('Server already exists on this network')
            return

        ### To accept additional servers, check to see if source server is already linked.
        ### Servers introduced by the source do not require authentication.
        if not self.linkAccept and not self.eos:
            self.linkAccept = True
            tempName = ' '.join(recv).split(':')[-2]
            self.hostname = tempName.split()[-2].strip()
            self.hopcount = tempName.split()[-1]
            self.name = ' '.join(recv[4:])
            self.rawname = ' '.join(recv[3:])
            if self.name.startswith(':'):
                self.name = self.name[1:]
            #self.introducedBy = localServer
            _print('{}Hostname for {} set: {}{}'.format(G, self, self.hostname, W), server=localServer)
            _print('{}Server name for {} set: {}{}'.format(G, self, self.name, W), server=localServer)
            _print('{}Hopcount for {} set: {}{}'.format(G, self, self.hopcount, W), server=localServer)

            ip, port = self.socket.getpeername()
            ip2, port2 = self.socket.getsockname()
            if self.hostname not in localServer.conf['link']:
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: not found in conf'.format(self.hostname, ip, port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration1'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send('ERROR :{}'.format(error))
                elif localServer.linkrequester[self]['user']:
                    localServer.linkrequester[self]['user'].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration1', silent=True)
                return
            ### Assign the class.
            self.cls = localServer.conf['link'][self.hostname]['class']
            _print('{}Class: {}{}'.format(G, self.cls, W), server=localServer)
            if not self.cls:
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: remote server has no class'.format(self.hostname, ip, port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration1'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send('ERROR :{}'.format(error))
                elif localServer.linkrequester[self]['user']:
                    localServer.linkrequester[self]['user'].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration')
                return
            totalClasses = list(filter(lambda s: s.cls == self.cls, localServer.servers))
            if len(totalClasses) > int(localServer.conf['class'][self.cls]['max']):
                self.quit('Maximum server connections for this class reached')
                return

            if self.linkpass:
                if self.linkpass != localServer.conf['link'][self.hostname]['pass']:
                    msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: wrong password'.format(self.hostname, ip, port)
                    error = 'Error connecting to server {}[{}:{}]: no matching link configuration2'.format(localServer.hostname, ip2, port2)
                    if self not in localServer.linkrequester:
                        self._send('ERROR :{}'.format(error))
                    elif localServer.linkrequester[self]['user']:
                        localServer.linkrequester[self]['user'].send('NOTICE', '*** {}'.format(msg))
                    self.quit('no matching link configuration2',silent=True)
                    return
            if not match(localServer.conf['link'][self.hostname]['incoming']['host'], ip):
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: incoming IP does not match'.format(self.hostname, ip,port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration3'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send('ERROR :{}'.format(error))
                elif localServer.linkrequester[self]['user']:
                    localServer.linkrequester[self]['user'].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration3', silent=True)
                return

            selfIntroduction(localServer, self)
            data = ':{} SID {} 0 {} {}'.format(localServer.sid, self.hostname, self.sid, self.name)
            localServer.new_sync(localServer, self, data)
            #selfIntroduction(localServer, self)
            ###
            for server in [server for server in localServer.servers if server.socket and server != self]:
                hopcount = int(server.hopcount) + 1
                sid = localServer.sid if server.socket else server.uplink.sid
                data = ':{} SID {} {} {} :{}'.format(sid, server.hostname, hopcount, server.sid, server.name)
                self._send(data)
            _print('Introduced all direct links first, now additional servers', server=localServer)
            for server in [server for server in localServer.servers if not server.socket and server != self]:
                hopcount = int(server.hopcount) + 1
                sid = localServer.sid if server.socket else server.uplink.sid
                data = ':{} SID {} {} {} :{}'.format(sid, server.hostname, hopcount, server.sid, server.name)
                self._send(data)
                #sync_users(self, localServer, sid)
                ### Sync <server> users.
                #print('Sending to {}: {}'.format(self, data))
            syncData(localServer, self, None)
            return

            '''
            if self in localServer.syncDone:
                #print('{}Received SERVER command from remote server {}, but I have already synced to it.{}'.format(R, self.hostname, W))
                return

            if self in localServer.linkrequester:
                ### This must also being triggered upon auto-link.
                syncData(localServer, self, None)
            else:
                selfIntroduction(localServer, self)
                return
            '''

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
        _print(e, server=localServer)

@ircd.Modules.params(4)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('sid')
def sid(self, localServer, recv):
    try:
        uplink = [s for s in localServer.servers if s.sid == recv[0][1:]]
        if not uplink:
            self._send('ERROR :Could not find uplink for {}'.format(recv[0][1:]))
            self.quit()
            return
        uplink = uplink[0]
        sid = recv[4]
        hostname = recv[2]
        checkSid(self, localServer, sid, hostname)

        hopcount = int(recv[3])

        if hostname == self.hostname:
            ### Own server?
            return

        from ircd import Server
        newServer = Server(origin=localServer,serverLink=True)

        newServer.hostname = hostname

        newServer.hopcount = hopcount
        newServer.name = ' '.join(recv[5:])[1:]

        newServer.introducedBy = self
        newServer.uplink = uplink
        newServer.sid = sid
        _print('{}New server added to the network: {}{}'.format(G, newServer.hostname, W), server=localServer)
        _print('{}SID: {}{}'.format(G, newServer.sid, W), server=localServer)
        _print('{}Introduced by: {} ({}) {}'.format(G, newServer.introducedBy.hostname, newServer.introducedBy.sid, W), server=localServer)
        _print('{}Uplinked to: {} ({}) {}'.format(G, newServer.uplink.hostname, newServer.uplink.sid, W), server=localServer)
        _print('{}Hopcount: {}{}'.format(G, newServer.hopcount, W), server=localServer)
        ### How many hops do I need to reach newServer? == hopcount

        localServer.new_sync(localServer, self, ' '.join(recv))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj,W)
        _print(e, server=localServer)
