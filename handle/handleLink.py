#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import time
import threading
import socket
import importlib
import ast
import hashlib
import ssl
from handle.functions import _print, IPtoBase64

if sys.version_info[0] < 3:
    print('Python 2 is not supported.')
    sys.exit()

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
R2 = '\033[91m' # bright red
G = '\033[32m' # green
G2 = '\033[92m' # bright green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

def syncChannels(localServer, newServer):
    for c in localServer.channels:
        if len(c.users) == 0 or c.name[0] == '&':
            continue
        modeparams = []
        for mode in c.modes:
            if mode == 'k' and c.key:
                modeparams.append(c.key)
            if mode == 'l':
                modeparams.append(str(c.limit))
        modeparams = ' {}'.format(' '.join(modeparams)) if len(modeparams) > 0 else '{}'.format(' '.join(modeparams))
        memberlist, banlist, excepts, invex, prefix = [], [], [], [], ''
        for user in [user for user in c.users if '^' not in user.modes]:
            if 'q' in c.usermodes[user]:
                prefix += '*'
            if 'a' in c.usermodes[user]:
                prefix += '~'
            if 'o' in c.usermodes[user]:
                prefix += '@'
            if 'h' in c.usermodes[user]:
                prefix += '%'
            if 'v' in c.usermodes[user]:
                prefix += '+'

            member = '{}{}'.format(prefix, user.uid)
            prefix = ''
            memberlist.append(member)

        if not memberlist:
            continue

        memberlist = ' '.join(memberlist)
        for b in c.bans:
            banlist.append(b)
        for e in c.excepts:
            excepts.append(e)
        for I in c.invex:
            invex.append(I)

        b = ' '.join(['&' + x for x in banlist])
        e = ' '.join(['"' + x for x in excepts])
        I = ' '.join(["'" + x for x in invex])
        data = '{} {} +{}{} :{} {} {} {}'.format(c.creation, c.name, c.modes, modeparams, memberlist, b, e, I)

        newServer._send(':{} SJOIN {}'.format(localServer.sid, data))
        if c.topic != '':
            data = ':{} TOPIC {} {} {} :{}'.format(localServer.sid, c.name, c.topic_author, c.topic_time, c.topic)
            newServer._send(data)

def selfIntroduction(localServer, newServer, outgoing=False):
    try:
        if newServer not in localServer.introducedTo:
            if outgoing:
                destPass = localServer.conf['link'][newServer.hostname]['pass']
                newServer._send(':{} PASS :{}'.format(localServer.sid, destPass))
            server_support = ' '.join(localServer.server_support)
            newServer._send(':{} PROTOCTL EAUTH={} SID={} {}'.format(localServer.sid, localServer.hostname, localServer.sid, server_support))
            newServer._send(':{} PROTOCTL NOQUIT NICKv2 CLK SJOIN SJOIN2 UMODE2 VL SJ3 TKLEXT TKLEXT2 NICKIP ESVID EXTSWHOIS'.format(localServer.sid))
            ### :version-sid
            version = 'P{}-{}'.format(localServer.versionnumber.replace('.', ''), localServer.sid)
            local_modules = [m.__name__ for m in localServer.modules]
            modlist = []
            for entry in local_modules:
                totlen = len(' '.join(modlist))
                if totlen >= 400:
                    newServer._send('MODLIST :{}'.format(' '.join(modlist)))
                    modlist = []
                modlist.append(entry)
            if modlist:
                newServer._send('MODLIST :{}'.format(' '.join(modlist)))

            newServer._send('SERVER {} 1 :{} {}'.format(localServer.hostname, version, localServer.name))
            #else:
            #    newServer._send(':{} SID {} 1 {} :{}'.format(localServer.sid, localServer.hostname, localServer.sid, localServer.name))
            _print('{}Introduced myself to {}. Expecting remote sync sequence...{}'.format(Y, newServer.hostname, W))
        localServer.introducedTo.append(newServer)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj,W)
        _print(e, server=localServer)

def syncUsers(localServer, newServer):
    try:
        totalServers = [localServer]+localServer.servers
        for server in [server for server in totalServers if server != newServer and server.introducedBy != newServer and newServer.introducedBy != server and server not in newServer.syncDone and newServer.socket]:
            newServer.syncDone.append(server)
            _print('{}Syncing info from {} to {}{}'.format(Y, server.hostname, newServer.hostname, W), server=localServer)
            for u in [u for u in localServer.users if u.server == server and u.registered]:
                ip = IPtoBase64(u.ip)
                if not ip:
                    ip = '*'
                hopcount = str(u.server.hopcount + 1)
                data = ':{} UID {} {} {} {} {} {} 0 +{} {} {} {} :{}'.format(server.sid, u.nickname, hopcount, u.signon, u.ident, u.hostname, u.uid, u.modes, u.cloakhost, u.cloakhost, ip, u.realname)
                _print('<<< {}'.format(data), server=localServer)
                newServer._send(data)
                if u.fingerprint:
                    data = 'MD client {} certfp :{}'.format(u.uid, u.fingerprint)
                    newServer._send(':{} {}'.format(server.sid, data))
                if u.operaccount:
                    data = 'MD client {} operaccount :{}'.format(u.uid, u.operaccount)
                    newServer._send(':{} {}'.format(server.sid, data))
                if u.snomasks:
                    newServer._send(':{} BV +{}'.format(u.uid, u.snomasks))
                if 'o' in u.modes:
                    for line in u.swhois:
                        newServer._send(':{} SWHOIS {} :{}'.format(server.sid, u.uid, line))
                if u.away:
                    newServer._send(':{} AWAY :{}'.format(u.uid, u.away))
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj,W)
        _print(e, server=localServer)

def syncData(localServer, newServer, serverIntroducer, selfRequest=True):
    if selfRequest:
        _print('{}Local server requested the link.{}'.format(Y, W), server=localServer)
    else:
        _print('{}Remote server requested the link.{}'.format(Y, W), server=localServer)

    #selfIntroduction(localServer, newServer)

    if localServer.users:
        syncUsers(localServer, newServer)
    if localServer.channels:
        syncChannels(localServer, newServer)

    ### Sync global TKL. I think I should move this up a bit.
    try:
        for type in localServer.tkl:
            for entry in localServer.tkl[type]:
                if not localServer.tkl[type][entry]['global']:
                    continue
                if type.lower() in 'gz':
                    mask = '{} {}'.format(entry.split('@')[0], entry.split('@')[1])
                elif type.lower() == 'q':
                    mask = '* {}'.format(entry)
                setter = localServer.tkl[type][entry]['setter']
                try:
                    source = list(filter(lambda s: s.hostname == setter, localServer.servers))
                    if source:
                        if source[0].hostname == newServer.hostname or source[0].introducedBy == newServer:
                            continue
                except:
                    pass
                expire = localServer.tkl[type][entry]['expire']
                ctime = localServer.tkl[type][entry]['ctime']
                reason = localServer.tkl[type][entry]['reason']
                data = ':{} TKL + {} {} {} {} {} :{}'.format(localServer.sid, type, mask, setter, expire, ctime, reason)
                newServer._send(data)
    except Exception as ex:
        _print(str(ex), server=localServer)
    _print('{}Server {} is done syncing to {}, sending EOS.{}'.format(Y, localServer.hostname, newServer.hostname, W), server=localServer)
    newServer._send(':{} EOS'.format(localServer.sid))
    #for server in [server for server in localServer.servers if server != newServer and server.sid and server.introducedBy == newServer]:
    #    _print('Sending also EOS from {} to {}'.format(server.hostname, newServer.hostname), server=localServer)
    #    newServer._send(':{} EOS'.format(server.sid))

    #00B NETINFO maxglobal currenttime protocolversion cloakhash networkname
    if newServer not in localServer.syncDone:
        cloakhash = localServer.conf['settings']['cloak-key']
        cloakhash = hashlib.md5(cloakhash.encode('utf-8')).hexdigest()
        data = ':{} NETINFO {} {} {} MD5:{} 0 0 0 :{}'.format(localServer.sid, localServer.maxgusers, int(time.time()), localServer.versionnumber.replace('.', ''), cloakhash, localServer.name)
        newServer._send(data)
        localServer.syncDone.append(newServer)

    _print('Sending PONG to {} (end of syncData)'.format(newServer.hostname), server=localServer)
    newServer._send(':{} PONG {}'.format(localServer.sid, newServer.hostname))
    return

class Link(threading.Thread):
    def __init__(self, origin=None, localServer=None, name=None, host=None, port=None, pswd=None, is_ssl=False, autoLink=False, incoming=True):
        threading.Thread.__init__(self)
        self.origin = origin
        self.localServer = localServer
        self.name = name
        self.pswd = pswd
        self.host = host
        self.port = port
        self.is_ssl = is_ssl
        self.autoLink = autoLink

    def run(self):
        try:
            exists = list(filter(lambda s: s.hostname == self.name, self.localServer.servers+[self.localServer]))
            if exists:
                _print('Server {} already exists on this network'.format(exists[0].hostname), server=self.localServer)
                #self.quit('Server already exists on this network')
                return

            serv = None
            if not self.host.replace('.', '').isdigit():
                self.host = socket.gethostbyname(self.host)
            self.socket = socket.socket()
            if self.is_ssl:
                self.socket = ssl.wrap_socket(self.socket)
                _print('Wrapped outgoing socket {} in SSL'.format(self.socket), server=self.localServer)
            self.socket.settimeout(5)
            self.socket.connect((self.host, self.port))

            from ircd import Server
            serv = Server(origin=self.localServer, serverLink=True, sock=self.socket, is_ssl=self.is_ssl)
            serv.hostname = self.name
            serv.ip = self.host
            serv.port = self.port
            # Requesting and authing link to remote server.
            if self.origin or self.autoLink:
                self.localServer.linkrequester[serv] = self.origin

            selfIntroduction(self.localServer, serv, outgoing=True)
            '''
            serv._send(':{} PASS :{}'.format(self.localServer.sid, self.pswd))
            server_support = ' '.join(self.localServer.server_support)
            serv._send(':{} PROTOCTL EAUTH={} SID={} {}'.format(self.localServer.sid, self.localServer.hostname, self.localServer.sid, server_support))
            serv._send(':{} PROTOCTL NOQUIT NICKv2 SJOIN EXTSWHOIS CLK SJOIN2 UMODE2 VL SJ3 TKLEXT TKLEXT2 NICKIP ESVID'.format(self.localServer.sid))
            ### Sending modlis.
            local_modules = [m.__name__ for m in self.localServer.modules]
            modlist = []
            for entry in local_modules:
                totlen = len(' '.join(modlist))
                if totlen >= 400:
                    serv._send('MODLIST :{}'.format(' '.join(modlist)))
                    modlist = []
                modlist.append(entry)
            if modlist:
                serv._send('MODLIST :{}'.format(' '.join(modlist)))
                serv._send(':{} SERVER {} 1 :{}'.format(self.localServer.sid, self.localServer.hostname, self.localServer.name))
            '''
            if serv not in self.localServer.introducedTo:
                self.localServer.introducedTo.append(serv)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{} EXCEPTION: {} in file {} line {}: {}'.format(self.name, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
            _print(e, server=self.localServer)

            if serv:
                serv.quit(str(ex))
            if self.origin:
                self.origin.send('NOTICE', '*** Error connecting to server {}[{}:{}]: {}'.format(self.name, self.host, self.port, ex))
            if self.is_ssl:
                self.origin.send('NOTICE', '*** Make sure SSL is enabled on both ends and ports are listening for SSL connections'.format(self.name, self.host, self.port, ex))
        finally:
            if self.name.lower() in self.localServer.pendingLinks:
                self.localServer.pendingLinks.remove(self.name.lower())
