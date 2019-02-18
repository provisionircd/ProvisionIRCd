#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gc
gc.enable()

#from pympler.tracker import SummaryTracker
#tracker = SummaryTracker()
#from mem_top import mem_top

from handle.functions import _print, match, TKL, cloak, IPtoBase64, Base64toIP, show_support, check_flood

#from handle import handleMemory as mem

import random
import time
import string
import os
import sys
import socket
import importlib
import datetime
import threading
#import psutil
#import objgraph

if sys.version_info[0] < 3:
    print('Python 2 is not supported.')
    sys.exit()

def RevIP(ip):
    x = 3
    revip = ''
    while 1:
        if revip:
            revip = revip + '.' + ip.split('.')[x]
        else:
            revip = ip.split('.')[x]
        if x == 0:
            break
        x -= 1
    return revip

class DNSBLCheck(threading.Thread):
    def __init__(self, localServer, u, ip):
        self.localServer = localServer
        self.u = u
        self.ip = ip
        threading.Thread.__init__(self)

    def run(self):
        if self.ip in self.localServer.dnsblCache:
            reason = 'Your IP is blacklisted by {}'.format(self.localServer.dnsblCache[self.ip]['bl']+' [cached]')
            self.u._send(':{} 304 * :{}'.format(self.localServer.hostname, reason))
            self.u.quit(reason)
            return
        if self.ip in set(self.localServer.bannedList):
            self.u._send(':{} 304 * :Your IP has been banned (listed locally).'.format(self.localServer.hostname))
            self.u.quit('Your IP has been banned (listed locally)')
            return

        for x in [x for x in self.localServer.conf['dnsbl']['list'] if '.' in x]:
            try:
                result = socket.gethostbyname(RevIP(self.ip)+ '.' + x)
                reason = 'Your IP is blacklisted by {}'.format(x)
                if self.ip not in self.localServer.dnsblCache:
                    self.localServer.dnsblCache[self.ip] = {}
                    self.localServer.dnsblCache[self.ip]['bl'] = x
                    self.localServer.dnsblCache[self.ip]['ctime'] = int(time.time())
                self.u._send(':{} 304 * :{}'.format(self.localServer.hostname, reason))
                msg = '*** DNSBL match for IP {}: {} [nick: {}]'.format(self.u.ip, x, self.u.nickname)
                self.localServer.snotice('d', msg)
                self.u.quit(reason)
                return
            except:
                pass

class User:
    def __init__(self, server, sock=None, address=None, is_ssl=None, serverClass=None, params=None):
        try:
            #mem.dump()
            self.socket = sock
            self.server = None
            self.cloakhost = '*'
            self.connected = True
            self.nickname = '*'
            self.ident = ''
            self.hostname = ''
            self.realname = ''
            self.svid = '*'
            self.channels = []
            self.modes = ''
            #self.opermodes = ''
            self.operflags = []
            self.snomasks = ''
            self.swhois = []
            self.watchlist = []
            self.caplist = []
            self.sends_cap = False
            self.cap_end = False
            self.watchC = False
            self.watchS = False
            self.ssl = is_ssl

            self.operaccount = ''
            self.away = False
            self.sendbuffer = ''
            self.operswhois = ''
            self.fingerprint = None

            self.flood_penalty = 0
            self.flood_penalty_time = 0

            if self.socket:
                self.server = server
                self.localServer = server
                self.addr = address
                self.ip, self.hostname = self.addr[0], self.addr[0]
                self.cls = None
                if 'dnsbl' in self.server.conf:
                    dnsbl_except = False
                    if 'except' in self.server.conf and 'dnsbl' in self.server.conf['except']:
                        for e in self.server.conf['except']['dnsbl']:
                            if match(e, self.ip):
                                dnsbl_except = True
                    if not dnsbl_except:
                        d = DNSBLCheck(self.server, self, self.ip)
                        d.start()

                self.registered = False
                self.signon = int(time.time())
                throttleTreshhold = int(self.server.conf['settings']['throttle'].split(':')[0])
                throttleTime = int(self.server.conf['settings']['throttle'].split(':')[1])
                totalConns = list(filter(lambda u: u.ip == self.ip and int(time.time()) - self.server.throttle[u]['ctime'] <= throttleTime, self.server.throttle))
                throttle_except = False
                if 'except' in self.server.conf and 'throttle' in self.server.conf['except']:
                    for e in self.server.conf['except']['throttle']:
                        if match(e, self.ip):
                            throttle_except = True
                if len(totalConns) >= throttleTreshhold and not throttle_except:
                    self.quit('Throttling - You are (re)connecting too fast')
                    return

                self.server.throttle[self] = {}
                self.server.throttle[self]['ip'] = self.ip
                self.server.throttle[self]['ctime'] = int(time.time())

                self.uid = '{}{}'.format(self.server.sid, ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6)))
                while list(filter(lambda u: u.uid == self.uid, self.server.users)):
                    self.uid = '{}{}'.format(self.server.sid, ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6)))

                self.ping = int(time.time())
                self.lastPingSent = int(time.time())
                self.server.users.append(self)
                self.recvbuffer = ''
                self.validping = False
                self.server.totalcons += 1

                TKL.check(self, self.server, self, 'z')
                TKL.check(self, self.server, self, 'Z')

                if self.ssl and self.socket:
                    try:
                        fp = self.socket.getpeercert()
                        if fp:
                            self.fingerprint = hashlib.sha256(repr(fp).encode('utf-8')).hexdigest()
                    except:
                        pass

                self.idle = int(time.time())

                if self.ip in self.server.hostcache:
                    self.hostname = self.server.hostcache[self.ip]['host']
                    self._send(':{} NOTICE AUTH :*** Found your hostname ({}) [cached]'.format(self.server.hostname, self.hostname))
                elif 'dontresolve' not in self.server.conf['settings'] or ('dontresolve' in self.server.conf['settings'] and not self.server.conf['settings']['dontresolve']):
                    try:
                        self.hostname = socket.gethostbyaddr(self.ip)[0]
                        self.hostname[1]
                        self.server.hostcache[self.ip] = {}
                        self.server.hostcache[self.ip]['host'] = self.hostname
                        self.server.hostcache[self.ip]['ctime'] = int(time.time())
                        self._send(':{} NOTICE AUTH :*** Found your hostname ({})'.format(self.server.hostname, self.hostname))
                    except Exception as ex:
                        self.hostname = self.ip
                        self._send(':{} NOTICE AUTH :*** Couldn\'t resolve your hostname; using IP address instead ({})'.format(self.server.hostname, self.hostname))
                else:
                    self._send(':{} NOTICE AUTH :*** Host resolution is disabled, using IP ({})'.format(self.server.hostname, self.ip))

                self.cloakhost = cloak(self.server, self.hostname)

                TKL.check(self, self.server, self, 'g')
                TKL.check(self, self.server, self, 'G')

            else:
                try:
                    ### :001 UID Sirius 1 1518982877 provision 109.201.133.76 001R909JRYW 0 +oixzshqW * root.provisionweb.org 109.201.133.76 :.
                    ### [':002', 'UID', 'asdf', '0', '1518983093', 'provision', '109.201.133.76', '002G6LYS067', '0', '+ixz', '*', '40a2f7ea.9d2b21c8.abbb717e.IP', '109.201.133.76', ':.']
                    ### :00B UID NickServ 1 1517540240 services services.host 00BAAAA6O * +qioS * * * :Nickname Registration Service
                    self.origin = serverClass
                    self.localServer = serverClass
                    self.origin.users.append(self)
                    self.cls = 0
                    self.nickname = params[2]
                    self.idle = int(params[4])
                    self.signon = int(params[4])
                    self.ident = params[5]
                    self.hostname = params[6]
                    self.uid = params[7]
                    server = list(filter(lambda s: s.sid == params[0][1:], self.localServer.servers))
                    if not server:
                        self.quit('Unknown connection')
                        return
                    self.server = server[0]
                    self.modes = params[9].strip('+')
                    if params[11] == '*':
                        self.cloakhost = params[6]
                    else:
                        self.cloakhost = params[11]
                    if params[12] != '*' and not params[12].replace('.', '').isdigit() and params[12] is not None:
                        ### If the IP position is not an actual IP.
                        self.ip = Base64toIP(params[12])
                    else:
                        self.ip = params[12]
                    TKL.check(self, self.origin, self, 'Z')
                    TKL.check(self, self.origin, self, 'G')
                    self.realname = ' '.join(params[13:])[1:]
                    self.registered = True
                    if len(self.origin.users) > self.origin.maxgusers:
                        self.origin.maxgusers = len(self.origin.users)

                    watch_notify = [user for user in self.origin.users if self.nickname.lower() in [x.lower() for x in user.watchlist]]
                    for user in watch_notify:
                        user.sendraw(600, '{} {} {} {} :logged online'.format(self.nickname, self.ident, self.cloakhost, self.signon))

                    #msg = '*** Remote client connecting: {} ({}@{}) {{{}}} [{}{}]'.format(self.nickname, self.ident, self.hostname, str(self.cls), 'secure' if 'z' in self.modes else 'plain', ' '+self.socket.cipher()[0] if self.ssl else '')
                    #self.server.snotice('C', msg)
                except Exception as ex:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                    _print(e, server=self.localServer)

            #_print('New user class {} successfully created'.format(self), server=self.localServer)
            gc.collect()

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
            _print(e, server=self.localServer)

    def __del__(self):
        #pass
        _print('User {} closed'.format(self, server=self.localServer))
        #objgraph.show_most_common_types()

    def handle_recv(self):
        try:
            while self.recvbuffer.find('\n') != -1:
                recv = self.recvbuffer[:self.recvbuffer.find('\n')]
                self.recvbuffer = self.recvbuffer[self.recvbuffer.find('\n')+1:]
                recv = recv.rstrip()
                if not recv:
                    self.recvbuffer = ''
                    self.flood_safe = False
                    continue
                localServer = self.server
                self.ping = int(time.time())

                self.flood_penalty += 1500 + len(recv)
                check_flood(localServer, self)

                if not self.flood_penalty_time:
                    self.flood_penalty_time = int(time.time())

                dont_parse = ['topic', 'swhois']
                command = recv.split()[0].lower()
                if command.lower() in dont_parse:
                    parsed = recv.split()
                else:
                    parsed = self.parse_command(recv)

                ignore = ['ping', 'pong', 'ison', 'watch', 'who', 'privmsg', 'notice']
                #ignore = []
                if command not in ignore:
                    #pass
                    _print('> {} :: {}'.format(self.nickname, recv), server=self.server)
                #print('ik ga zo slaaaaaapen maar jij bent ernie?')
                if type(self).__name__ == 'User' and command != 'nick' and command != 'user' and command != 'pong' and command != 'cap' and command != 'starttls' and not self.registered:
                    return self.sendraw(462, 'You have not registered')
                if command == 'pong':
                    if self.socket in self.server.pings:
                        ping = recv.split()[1]
                        if ping.startswith(':'):
                            ping = ping[1:]
                        if self.server.pings[self.socket] == ping:
                            del self.server.pings[self.socket]
                            self.validping = True
                            if self.ident != '' and self.nickname != '*' and (self.cap_end or not self.sends_cap):
                                self.welcome()
                false_cmd = True
                try:
                    cmd = importlib.import_module('cmds.cmd_'+command.lower())
                    getattr(cmd, 'cmd_'+command.upper())(self, localServer, parsed)
                    false_cmd = False
                except ImportError:
                    try:
                        alias = localServer.conf['aliases']
                        if alias[command.lower()]['type'] == 'services':
                            service = list(filter(lambda u: u.nickname == alias[command.lower()]['target'] and 'services' in localServer.conf['settings'] and u.server.hostname == localServer.conf['settings']['services'], localServer.users))
                            if not service:
                                return self.sendraw(440, ':Services are currently down. Please try again later.')
                        #print('forming data')
                        data = '{} :{}'.format(alias[command.lower()]['target'], ' '.join(recv.split()[1:]))
                        self.handle('PRIVMSG', data)
                        return
                    except KeyError:
                        pass

                ### Checking hooked commands.
                #if command.lower() not in ignore:
                    #print('Checking for hooked commands for {}'.format(command))
                for callable in [callable for callable in localServer.commands if callable[0].lower() == command.lower()]:
                    try:
                        ### (cmd, callable, params, req_modes, req_flags, req_class, module)
                        #print('from handle recv: {}'.format(callable))
                        got_params = len(parsed) - 1
                        req_params = callable[2]
                        req_modes = callable[3]
                        req_flags = callable[4]
                        req_class = callable[5]
                        module = callable[6]
                        if type(self).__name__ != req_class:
                            ### Wrong class!
                            if req_class == 'Server':
                                return self.sendraw(487, ':{} is a server only command'.format(command.upper()))
                        if got_params < req_params:
                            return self.sendraw(461, ':{} Not enough parameters. Required: {}'.format(command.upper(), req_params))
                    except Exception as ex:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                        _print(e, server=localServer)

                    ### Check modes.
                    if req_modes:
                        req_modes = ' '.join(req_modes)
                        if 'o' in req_modes and 'o' not in self.modes:
                            return self.sendraw(481, ':Permission denied - You are not an IRC Operator')
                        forbid = set(req_modes).difference(set(self.modes))
                        if forbid:
                            return self.sendraw(481, ':Permission denied - Required mode not set')
                    ### Check flags.
                    forbid = True
                    if req_flags:
                        for flag in req_flags:
                            if '|' in flag:
                                ### Either flag is good.
                                if list(filter(lambda f: f in self.operflags, flag.split('|'))):
                                    forbid = False
                                    break
                            else:
                                forbid = set(req_flags).difference(set(self.operflags))
                                break
                        if forbid:
                            return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
                    try:
                        false_cmd = False
                        ### Do not add a return here, it will interfere with select().
                        ### On the plus side, you'll save some money on a haircut.
                        callable[1](self, localServer, parsed)

                    except Exception as ex:
                        _print('Exception in module {}: {}'.format(module, ex), server=localServer)
                if false_cmd:
                    self.sendraw(421, '{} :Unknown command you foolish user'.format(command.upper()))

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
            _print(e, server=localServer)

    def parse_command(self, data):
        xwords = data.split(' ')
        words = []
        for i in range(len(xwords)):
            word = xwords[i]
            if word.startswith(':'):
                words.append(' '.join([word[1:]] + xwords[i+1:]))
                break
            words.append(word)
        words = list(filter(None, words))
        return words

    def _send(self, data, direct=False):
        if self.socket:
            self.sendbuffer += data + '\r\n'
            ignore = ['ping', 'pong', 'ison', '303']
            #if data.split()[1].lower() not in set(ignore):
            #    print('< {} :: {}'.format(self.nickname, data))

    def send(self, command, data, direct=False):
        self._send(':{} {} {} {}'.format(self.server.hostname, command, self.nickname, data), direct=direct)

    def sendraw(self, numeric, data):
        self.send(str(numeric).rjust(3, '0'), data)

    def broadcast(self, users, data, source=None):
        ### Source must be a class.
        if source:
            if type(source).__name__ == 'Server':
                source = source.hostname
            else:
                source = source.fullmask()
        else:
            source = self.fullmask()

        for user in users:
            user._send(':{} {}'.format(source, data))

    def setinfo(self, info, t='', source=None):
        try:
            if not info or not type:
                return
            if not source:
                _print('No source provided in setinfo()!', server=self.localServer)
                return
            if type(source) == str or type(source).__name__ != 'Server':
                _print('Wrong source type provided in setinfo(): {}'.format(source), server=self.localServer)
                return
            if t not in ['host', 'ident']:
                _print('Incorrect type received in setinfo(): {}'.format(t), server=self.localServer)
                return
            valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
            for c in str(info):
                if c.lower() not in valid:
                    info = info.replace(c, '')
            updated = []
            if self.registered:
                for user in self.localServer.users:
                    for user in [user for user in self.localServer.users if 'chghost' in user.caplist and user not in updated and user.socket]:
                        common_chan = list(filter(lambda c: user in c.users and self in c.users, self.localServer.channels))
                        if not common_chan:
                            continue
                        user._send(':{} CHGHOST {} {}'.format(self.fullmask(), info if t == 'ident' else self.ident, info if t == 'host' else self.cloakhost))
                        updated.append(user)
            if t == 'host':
                self.cloakhost = info
            elif t == 'ident':
                self.ident = info

            if self.registered:
                data = ':{} {} {}'.format(self.uid, 'SETHOST' if t == 'host' else 'SETIDENT', self.cloakhost if t == 'host' else self.ident)
                self.localServer.new_sync(self.localServer, source, data)
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
            _print(e, server=self.localServer)

    def welcome(self):
        if not self.registered:
            for cls in self.server.conf['allow']:
                if 'ip' in self.server.conf['allow'][cls]:
                    clientmask = '{}@{}'.format(self.ident, self.ip)
                    isMatch = match(self.server.conf['allow'][cls]['ip'], clientmask)
                if 'hostname' in self.server.conf['allow'][cls]:
                    clientmask = '{}@{}'.format(self.ident, self.hostname)
                    isMatch = match(self.server.conf['allow'][cls]['hostname'], clientmask)
                if isMatch:
                    if 'options' in self.server.conf['allow'][cls]:
                        if 'ssl' in self.server.conf['allow'][cls]['options'] and not self.ssl:
                            continue
                    self.cls = cls
                    break

            if not self.cls:
                self.quit('You are not authorized to connect to this server')
                return

            totalClasses = list(filter(lambda u: u.registered and u.server == self.server and u.cls == self.cls, self.server.users))
            if len(totalClasses) > int(self.server.conf['class'][self.cls]['max']):
                self.quit('Maximum connections for this class reached')
                return

            #### Check maxperip for the class. Only count local connections.
            clones = list(filter(lambda u: u.registered and u.socket and u.ip == self.ip, self.server.users))
            if len(clones) > int(self.server.conf['allow'][self.cls]['maxperip']):
                self.quit('Maximum connections from your IP')
                return

            current_lusers = len([user for user in self.server.users if user.server == self.server])
            if current_lusers > self.server.maxusers:
                self.server.maxusers = current_lusers

            msg = '*** Client connecting: {} ({}@{}) {{{}}} [{}{}]'.format(self.nickname, self.ident, self.hostname, self.cls, 'secure' if self.ssl else 'plain', ' '+self.socket.cipher()[0] if self.ssl else '')
            self.server.snotice('c', msg)

            if len(self.server.users) > self.server.maxgusers:
                self.server.maxgusers = len(self.server.users)
                if self.server.maxgusers % 10 == 0:
                    self.server.snotice('s', '*** New global user record: {}'.format(self.server.maxgusers))

            self.sendraw('001', ':Welcome to the {} IRC Network {}!{}@{}'.format(self.server.name, self.nickname, self.ident, self.hostname))
            self.sendraw('002', ':Your host is {}, running version {}'.format(self.server.hostname, self.server.version))
            d = datetime.datetime.fromtimestamp(self.server.creationtime).strftime('%a %b %d %Y')
            t = datetime.datetime.fromtimestamp(self.server.creationtime).strftime('%H:%M:%S %Z')
            self.sendraw('003', ':This server was created {} at {}'.format(d, t))

            umodes, chmodes = '', ''
            for m in [m for m in self.server.user_modes if m.isalpha() and m not in umodes]:
                umodes += m
            for t in self.server.channel_modes:
                for m in [m for m in self.server.channel_modes[t] if m.isalpha() and m not in chmodes]:
                    chmodes += m
            umodes = ''.join(sorted(set(umodes)))
            chmodes = ''.join(sorted(set(chmodes)))

            self.sendraw('004', '{} {} {} {}'.format(self.server.hostname, self.server.version, umodes, chmodes))
            show_support(self, self.server)
            if self.ssl:
                self.send('NOTICE', ':*** You are connected to {} with {}-{}'.format(self.server.hostname, self.socket.version(), self.socket.cipher()[0]))
            self.handle('lusers')
            self.handle('motd')
            if self.fingerprint:
                self.send('NOTICE', ':*** Your SSL fingerprint is {}'.format(self.fingerprint))

            binip = IPtoBase64(self.ip)

            data = '{} {} {} {} {} {} 0 +{} {} {} {} :{}'.format(self.nickname, 0, self.signon, self.ident, self.hostname, self.uid, self.modes, self.cloakhost, self.cloakhost, binip, self.realname)

            self.server.syncToServers(self.server, self.server, ':{} UID {}'.format(self.server.sid, data))
            modes = []
            for mode in self.server.conf['settings']['modesonconnect']:
                if mode in self.server.user_modes and mode not in 'oqrzS':
                    modes.append(mode)
            if self.ssl:
                modes.append('z')
            if len(modes) > 0:
                p = {'override': True}
                self.handle('mode', '{} +{}'.format(self.nickname, ''.join(modes)), params=p)

            if self.fingerprint:
                data = 'MD client {} certfp :{}'.format(self.uid, self.fingerprint)
                # :irc.foonet.com MD client 001HBEI01 certfp :a6fc0bd6100a776aa3266ed9d5853d6dce563560d8f18869bc7eef811cb2d413
                self.server.syncToServers(self.server, self.server, ':{} {}'.format(self.server.sid, data))

            watch_notify = [user for user in self.server.users if self.nickname.lower() in [x.lower() for x in user.watchlist]]
            for user in watch_notify:
                user.sendraw(600, '{} {} {} {} :logged online'.format(self.nickname, self.ident, self.cloakhost, self.signon))

            self.registered = True

        gc.collect()

    def __repr__(self):
        return "<User '{}:{}'>".format(self.fullmask(), self.server.hostname)

    def fileno(self):
        return self.socket.fileno()

    def fullmask(self):
        return '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost)

    def fullrealhost(self):
        host = self.hostname if self.hostname != '' else self.ip
        return '{}{}{}'.format(self.nickname+'!' if self.nickname != '*' else '', self.ident+'@' if self.ident != '' else '', host)

    def chlevel(self, channel):
        localServer = self.server if self.socket else self.origin
        if self.server.hostname.lower() in set(localServer.conf['settings']['ulines']):
            return 10000
        elif self not in set(channel.users):
            return 0
        elif 'q' in channel.usermodes[self]:
            return 5
        elif 'a' in channel.usermodes[self]:
            return 4
        elif 'o' in channel.usermodes[self]:
            return 3
        elif 'h' in channel.usermodes[self]:
            return 2
        elif 'v' in channel.usermodes[self]:
            return 1
        else:
            return 0

    def ocheck(self, mode, flag, data=None):
        localServer = self.server if self.socket else self.localServer
        if (mode in self.modes and flag in self.operflags) or self.server.hostname.lower() in set(localServer.conf['settings']['ulines']):
            return True
        return False

    def quit(self, reason, error=True, banmsg=None, kill=False, broadcast=None, silent=False, source=None):
        try:
            localServer = self.localServer if not self.socket else self.server
            #print('HOE BEDOEL JE LOCALSERVER IS NIET DEFINED: {}'.format(localServer))
            sourceServer = source if source else self.server
            if not sourceServer.socket and sourceServer.uplink:
                sourceServer = sourceServer.uplink
            #_print('User {} quit, sourceServer: {}'.format(self, sourceServer), server=localServer)
            for callable in [callable for callable in localServer.events if callable[0].lower() == 'quit']:
                try:
                    ### 'quit' event will return a tuple: (success, broadcast)
                    ### broadcast is a list of all users to broadcast to.
                    ### This is useful for modules like m_delayjoin which modifies that list.
                    success, broadcast = callable[1](self, localServer, reason)
                except Exception as ex:
                    _print('Exception in module: {}: {}'.format(callable[2], ex), server=localServer)

            if banmsg:
                localServer.notice(self, '*** You are banned from this server: {}'.format(banmsg))

            while self.sendbuffer:
                _print('User {} has sendbuffer remaining: {}'.format(self, self.sendbuffer.rstrip()), server=localServer)
                ### Let's empty the sendbuffer manually.
                try:
                    sent = self.socket.send(bytes(self.sendbuffer + '\n', 'utf-8'))
                    self.sendbuffer = self.sendbuffer[sent:]
                except:
                    break

            if error and self.socket and reason:
                try:
                    self.socket.send(bytes('ERROR :Closing link: [{}] ({})\r\n'.format(self.fullrealhost(), reason), 'utf-8'))
                except:
                    pass

            if self.registered and (self.server == localServer or self.server.eos):
                if reason and not kill:
                    ### Look for servers with NOQUIT and add them to the skip list.
                    skip = [sourceServer]
                    for server in [server for server in localServer.servers if hasattr(server, 'protoctl') and 'NOQUIT' in server.protoctl and not server.eos]:
                        skip.append(server)
                    localServer.new_sync(localServer, skip, ':{} QUIT :{}'.format(self.uid, reason))

                if self.socket and reason and not silent:
                    localServer.snotice('c', '*** Client exiting: {} ({}@{}) ({})'.format(self.nickname, self.ident, self.hostname, reason))
            self.registered = False

            for channel in self.channels:
                if 'j' in channel.modes:
                    self.handle('PART', '{}'.format(channel.name))
                    continue

            if type(broadcast) != list: ### This must be checked against type.
                broadcast = []
                for channel in self.channels:
                    for user in channel.users:
                        if user not in set(broadcast) and user != self:
                            broadcast.append(user)

            if self.nickname != '*' and self.ident != '' and reason:
                self.broadcast(broadcast, 'QUIT :{}'.format(reason))

            for channel in list(self.channels):
                channel.users.remove(self)
                channel.usermodes.pop(self)
                if len(channel.users) == 0:
                    localServer.channels.remove(channel)
                self.channels.remove(channel)

            watch_notify_offline = [user for user in localServer.users if self.nickname.lower() in [x.lower() for x in user.watchlist]]
            for user in watch_notify_offline:
                user.sendraw(601, '{} {} {} {} :logged offline'.format(self.nickname, self.ident, self.cloakhost, self.signon))

            if self in localServer.users:
                localServer.users.remove(self)

            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_WR)
                except:
                    self.socket.close()

            del self

            gc.collect()

            #if localServer.forked:
            #    _print('Growth after self.quit() (if any):', server=localServer)
            #    objgraph.show_growth(limit=10)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
            _print(e, server=localServer)

    def handle(self, command, data=None, params=None):
        recv = '{} {}'.format(command, data if data else '')
        parsed = self.parse_command(recv)
        command = command.split()[0].lower()
        localServer = self.server if self.socket else self.origin
        try:
            cmd = importlib.import_module('cmds.cmd_'+command)
            if params:
                getattr(cmd, 'cmd_'+command.upper())(self, localServer, parsed, **params)
            else:
                getattr(cmd, 'cmd_'+command.upper())(self, localServer, parsed)
        except ImportError:
            for callable in [callable for callable in localServer.commands if callable[0].lower() == command]:
                ### (cmd, callable, params, req_modes, req_flags, req_class, module)
                got_params = len(parsed) - 1
                req_params = callable[2]
                req_modes = callable[3]
                req_flags = callable[4]
                if got_params < req_params:
                    return self.sendraw(461, ':{} Not enough parameters. Required: {}'.format(command.upper(), req_params))

                ### Check modes.
                if req_modes:
                    if 'o' in req_modes and 'o' not in self.modes:
                        return self.sendraw(481, ':Permission denied - You are not an IRC Operator')
                    forbid = set(req_modes).difference(set(self.modes))
                    if forbid:
                        return self.sendraw(481, ':Permission denied - Required mode not set')
                ### Check flags.
                if req_flags:
                    if '|' in req_flags:
                        ### Either flag is good.
                        req_flags = req_flags.split('|') # ['localkill', 'globalkill']
                    forbid = set(req_flags).difference(set(self.operflags))
                    if forbid:
                        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
                try:
                    if params:
                        callable[1](self, localServer, parsed, **params)
                    else:
                        callable[1](self, localServer, parsed)

                except Exception as ex:
                    _print('Exception in module {}: {}'.format(callable[6], ex), server=localServer)
