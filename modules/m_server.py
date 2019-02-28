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

@ircd.Modules.params(5)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('server')
def server(self, localServer, recv):
    try:
        exists = list(filter(lambda s: s.hostname.lower() == recv[2].lower(), localServer.servers+[localServer]))
        if exists and self != exists[0]:
            _print('Server {} already exists on this network2'.format(recv[2]), server=localServer)
            #self.quit('Server already exists on this network')
            return
        if not self.sid:
            _print('Direct link with {} denied because their SID is unknown to me'.format(recv[2]), server=localServer)
            self.quit('No SID received')
            return

        if not self.linkAccept and not self.eos:
            self.linkAccept = True
            tempName = ' '.join(recv).split(':')[-2]
            self.hostname = tempName.split()[-2].strip()
            self.hopcount = int(tempName.split()[-1])
            self.name = ' '.join(recv[4:])
            self.rawname = ' '.join(recv[3:])
            if self.name.startswith(':'):
                self.name = self.name[1:]

            _print('{}Hostname for {} set: {}{}'.format(G, self, self.hostname, W), server=localServer)
            _print('{}Server name for {} set: {}{}'.format(G, self, self.name, W), server=localServer)
            _print('{}Hopcount for {} set: {}{}'.format(G, self, self.hopcount, W), server=localServer)
            _print('{}SID for {} set: {}{}'.format(G, self, self.sid, W), server=localServer)


            ip, port = self.socket.getpeername()
            ip2, port2 = self.socket.getsockname()
            if self.hostname not in localServer.conf['link']:
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: not found in conf'.format(self.hostname, ip, port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration1'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send(':{} ERROR :{}'.format(localServer.sid, error))
                elif localServer.linkrequester[self]:
                    localServer.linkrequester[self].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration1')
                return

            self.cls = localServer.conf['link'][self.hostname]['class']
            _print('{}Class: {}{}'.format(G, self.cls, W), server=localServer)
            if not self.cls:
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: remote server has no class'.format(self.hostname, ip, port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration1'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send(':{} ERROR :{}'.format(localServer.sid, error))
                elif localServer.linkrequester[self]:
                    localServer.linkrequester[self].send('NOTICE', '*** {}'.format(msg))
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
                        self._send(':{} ERROR :{}'.format(localServer.sid, error))
                    elif localServer.linkrequester[self]:
                        localServer.linkrequester[self].send('NOTICE', '*** {}'.format(msg))
                    self.quit('no matching link configuration2')
                    return
            if not match(localServer.conf['link'][self.hostname]['incoming']['host'], ip):
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: incoming IP does not match'.format(self.hostname, ip,port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration3'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send(':{} ERROR :{}'.format(localServer.sid, error))
                elif localServer.linkrequester[self]:
                    localServer.linkrequester[self].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration3')
                return

            if self.hostname not in localServer.conf['settings']['ulines']:
                for cap in [cap.split('=')[0] for cap in localServer.server_support]:
                    if cap in self.protoctl:
                        _print('Cap {} is supported by both parties'.format(cap), server=localServer)
                    else:
                        self._send(':{} ERROR :Server {} is missing support for {}'.format(self.sid, self.hostname, cap))
                        self.quit('Server {} is missing support for {}'.format(self.hostname, cap))
                        return

            selfIntroduction(localServer, self)
            data = ':{} SID {} 1 {} {}'.format(localServer.sid, self.hostname, self.sid, self.name)
            localServer.new_sync(localServer, self, data)
            for server in [server for server in localServer.servers if server.sid and server != self]:
                sid = localServer.sid if server.socket else server.uplink.sid
                data = ':{} SID {} {} {} :{}'.format(sid, server.hostname, int(server.hopcount) + 1, server.sid, server.name)
                self._send(data)
            ''''
            _print('Introduced all direct links first, now additional servers', server=localServer)
            for server in [server for server in localServer.servers if not server.socket and server != self]:
                hopcount = int(server.hopcount) + 1
                sid = localServer.sid if server.socket else server.uplink.sid
                data = ':{} SID {} {} {} :{}'.format(sid, server.hostname, hopcount, server.sid, server.name)
                self._send(data)
            '''
            ### Only send this if we are the one requesting the link.
            if hasattr(self, 'outgoing') and self.outgoing:
                syncData(localServer, self)
            return

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
            self._send(':{} ERROR :Could not find uplink for {}'.format(localServer.sid, recv[0][1:]))
            self.quit()
            return
        uplink = uplink[0]
        sid = recv[4]
        hostname = recv[2]
        for server in [server for server in localServer.servers if server.sid == sid and server != self]:
            self._send(':{} ERROR :SID {} is already in use on that network'.format(localServer.sid, sid))
            self.quit('SID {} is already in use on that network'.format(sid))
            return

        hopcount = int(recv[3])

        if hostname == self.hostname:
            ### Own server?
            return

        from ircd import Server
        newServer = Server(origin=localServer, serverLink=True)

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

        localServer.new_sync(localServer, self, ' '.join(recv))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj,W)
        _print(e, server=localServer)
