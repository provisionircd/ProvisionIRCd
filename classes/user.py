try:
    import faulthandler
    faulthandler.enable()
except:
    pass
import gc
gc.enable()

from handle.functions import match, TKL, cloak, IPtoBase64, Base64toIP, show_support, check_flood, logging

import random
import time
import string
import sys
import socket
import importlib
import datetime
import threading
import hashlib
import select
import objgraph

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

class blacklist_check(threading.Thread):
    def __init__(self, user, blacklist):
        threading.Thread.__init__(self)
        self.user = user
        self.blacklist = blacklist
    def run(self):
        user = self.user
        blacklist = self.blacklist
        logging.debug('Looking up DNSBL query on {}: [{}]'.format(self.blacklist, user.ip))
        try:
            result = socket.gethostbyname(RevIP(user.ip)+ '.' + blacklist)
            reason = 'Your IP is blacklisted by {}'.format(blacklist)
            if user.ip not in user.server.dnsblCache:
                user.server.dnsblCache[user.ip] = {}
                user.server.dnsblCache[user.ip]['bl'] = blacklist
                user.server.dnsblCache[user.ip]['ctime'] = int(time.time())
                msg = '*** DNSBL match for IP {}: {} [nick: {}]'.format(user.ip, blacklist, user.nickname)
                user.server.snotice('d', msg)
            if user in user.server.users:
                user._send(':{} 304 * :{}'.format(user.server.hostname, reason))
            user.quit(reason)
        except:
            pass

def DNSBLCheck(self):
    user = self
    localServer = user.server
    if user.ip in localServer.dnsblCache:
        reason = 'Your IP is blacklisted by {}'.format(localServer.dnsblCache[user.ip]['bl']+' [cached]')
        for u in [u for u in list(localServer.users) if u.ip == user.ip]:
            u._send(':{} 304 * :{}'.format(localServer.hostname, reason))
            u.quit(reason)
        return
    if user.ip in localServer.bannedList:
        user._send(':{} 304 * :Your IP has been banned (listed locally).'.format(localServer.hostname))
        user.quit('Your IP has been banned (listed locally)')
        return

    for x in [x for x in localServer.conf['dnsbl']['list'] if '.' in x]:
        if user in user.server.users:
            b = blacklist_check(user, x)
            b.start()

READ_ONLY = (
    select.POLLIN |
    select.POLLPRI |
    select.POLLHUP |
    select.POLLERR
)
READ_WRITE = READ_ONLY | select.POLLOUT

def resolve_ip(self):
    try:
        ip_resolved = socket.gethostbyaddr(self.ip)[0]
    except socket.herror: ### Not a typo.
        ip_resolved = self.ip
    except Exception as ex:
        logging.exception(ex)
    deny_except = False
    if 'except' in self.server.conf and 'deny' in self.server.conf['except']:
        for e in self.server.conf['except']['deny']:
            if match(e, self.ident+'@'+ip_resolved) or match(e, self.ident+'@'+self.ip):
                deny_except = True
                break
    if not deny_except:
        for entry in self.server.deny:
            if match(entry, self.ident+'@'+ip_resolved) or match(entry, self.ident+'@'+self.ip):
                return self.quit('Your host matches a deny block, and is therefore not allowed.')

class User:
    def __init__(self, server, sock=None, address=None, is_ssl=None, serverClass=None, params=None):
        try:
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
                threading.Thread(target=resolve_ip, args=([self])).start()
                self.cls = None
                self.signon = int(time.time())
                self.registered = False
                self.ping = int(time.time())
                self.recvbuffer = ''
                self.validping = False
                self.server.users.append(self)
                for callable in [callable for callable in server.hooks if callable[0].lower() == 'new_connection']:
                    try:
                        callable[2](self, server)
                    except Exception as ex:
                        logging.exception(ex)
                if 'dnsbl' in self.server.conf:
                    #self.sendraw('020', ':Please wait while we process your connection.')
                    dnsbl_except = False
                    if 'except' in self.server.conf and 'dnsbl' in self.server.conf['except']:
                        for e in self.server.conf['except']['dnsbl']:
                            if match(e, self.ip):
                                dnsbl_except = True
                                break
                    if not dnsbl_except:
                        DNSBLCheck(self)

                TKL.check(self, self.server, self, 'z')
                TKL.check(self, self.server, self, 'Z')

                throttleTreshhold = int(self.server.conf['settings']['throttle'].split(':')[0])
                throttleTime = int(self.server.conf['settings']['throttle'].split(':')[1])
                totalConns = list(filter(lambda u: u.ip == self.ip and int(time.time()) - self.server.throttle[u]['ctime'] <= throttleTime, self.server.throttle))
                throttle_except = False
                if 'except' in self.server.conf and 'throttle' in self.server.conf['except']:
                    for e in self.server.conf['except']['throttle']:
                        if match(e, self.ip):
                            throttle_except = True
                if len(totalConns) >= throttleTreshhold and not throttle_except:
                    return self.quit('Throttling - You are (re)connecting too fast')

                self.server.throttle[self] = {}
                self.server.throttle[self]['ip'] = self.ip
                self.server.throttle[self]['ctime'] = int(time.time())

                self.uid = '{}{}'.format(self.server.sid, ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6)))
                while [u for u in self.server.users if hasattr(u, 'uid') and u != self and u.uid == self.uid]:
                #while list(filter(lambda u: u.uid == self.uid, self.server.users)):
                    self.uid = '{}{}'.format(self.server.sid, ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6)))

                self.lastPingSent = time.time() * 1000
                self.lag_measure = self.lastPingSent
                self.server.totalcons += 1
                if self.ssl and self.socket:
                    try:
                        fp = self.socket.getpeercert(binary_form=True)
                        if fp:
                            self.fingerprint = hashlib.sha256(repr(fp).encode('utf-8')).hexdigest()
                    except Exception as ex:
                        logging.exception(ex)

                self.idle = int(time.time())
                if self.ip in self.server.hostcache:
                    self.hostname = self.server.hostcache[self.ip]['host']
                    self._send(':{} NOTICE AUTH :*** Found your hostname ({}) [cached]'.format(self.server.hostname, self.hostname))
                elif 'dontresolve' not in self.server.conf['settings'] or ('dontresolve' in self.server.conf['settings'] and not self.server.conf['settings']['dontresolve']):
                    try:
                        self.hostname = socket.gethostbyaddr(self.ip)[0]
                        if not self.hostname.split('.')[1]:
                            raise
                        self.server.hostcache[self.ip] = {}
                        self.server.hostcache[self.ip]['host'] = self.hostname
                        self.server.hostcache[self.ip]['ctime'] = int(time.time())
                        self._send(':{} NOTICE AUTH :*** Found your hostname ({})'.format(self.server.hostname, self.hostname))
                    except Exception as ex:
                        self.hostname = self.ip
                        self._send(':{} NOTICE AUTH :*** Couldn\'t resolve your hostname; using IP address instead ({})'.format(self.server.hostname, self.hostname))
                else:
                    self._send(':{} NOTICE AUTH :*** Host resolution is disabled, using IP ({})'.format(self.server.hostname, self.ip))

                TKL.check(self, self.server, self, 'g')
                TKL.check(self, self.server, self, 'G')

                self.cloakhost = cloak(self.server, self.hostname)

            else:
                try:
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
                        logging.debug('Quitting {} because their server does not exist'.format(self.nickname), server=self.localServer)
                        self.quit('Unknown connection')
                        return
                    self.server = server[0]
                    self.modes = params[9].strip('+')
                    if params[11] == '*':
                        self.cloakhost = params[6]
                    else:
                        self.cloakhost = params[11]
                    if params[12] != '*' and not params[12].replace('.', '').isdigit() and params[12] is not None:
                        self.ip = Base64toIP(params[12])
                    else:
                        self.ip = params[12]
                    self.realname = ' '.join(params[13:])[1:]
                    self.registered = True
                    TKL.check(self, self.origin, self, 'Z')
                    TKL.check(self, self.origin, self, 'G')
                    if len(self.origin.users) > self.origin.maxgusers:
                        self.origin.maxgusers = len(self.origin.users)

                    watch_notify = [user for user in self.origin.users if self.nickname.lower() in [x.lower() for x in user.watchlist]]
                    for user in watch_notify:
                        user.sendraw(600, '{} {} {} {} :logged online'.format(self.nickname, self.ident, self.cloakhost, self.signon))

                    #msg = '*** Remote client connecting: {} ({}@{}) {{{}}} [{}{}]'.format(self.nickname, self.ident, self.hostname, str(self.cls), 'secure' if 'z' in self.modes else 'plain', ' '+self.socket.cipher()[0] if self.ssl else '')
                    #self.server.snotice('C', msg)
                except Exception as ex:
                    logging.exception(ex)
            #logging.info('New user class {} successfully created'.format(self))
            gc.collect()

        except Exception as ex:
            logging.exception(ex)

    def __del__(self):
        pass
        #logging.debug('User {} closed'.format(self))
        #objgraph.show_most_common_types()
        '''
        reflist = gc.get_referrers(self)
        if reflist:
            logging.debug('Found these references after __del__:')
            for r in reflist:
                logging.debug(r)
        else:
            logging.debug('Excellent, no more references after __del__!')
        '''

    def handle_recv(self):
        try:
            while self.recvbuffer.find('\n') != -1:
                recv = self.recvbuffer[:self.recvbuffer.find('\n')]
                self.recvbuffer = self.recvbuffer[self.recvbuffer.find('\n')+1:]
                recv = recv.rstrip(' \n\r')
                if not recv:
                    continue

                localServer = self.server
                command = recv.split()[0].lower()

                self.ping = int(time.time())
                if not hasattr(self, 'flood_safe') or not self.flood_safe:
                    self.flood_penalty += 1000 + len(recv)
                check_flood(localServer, self)

                if not self.flood_penalty_time:
                    self.flood_penalty_time = int(time.time())

                dont_parse = ['topic', 'swhois', 'prop']
                if command in dont_parse:
                    parsed = recv.split(' ')
                else:
                    parsed = self.parse_command(recv)

                ignore = ['ping', 'pong', 'ison', 'watch', 'who', 'privmsg', 'notice', 'ns', 'cs', 'nickserv', 'chanserv', 'id', 'identify', 'login', 'auth']
                #ignore = []
                if command not in ignore:
                    pass
                    #_print('> {} :: {}'.format(self.nickname, recv), server=self.server)

                # Looking for API calls.
                if not self.registered:
                    for callable in [callable for callable in self.server.api if callable[0].lower() == command.lower()]:
                        api_func = callable[1]
                        api_host = callable[2]
                        api_password = callable[3]
                        if api_host and not match(api_host, self.ip):
                            self.quit('API', api=1)
                            break
                        if api_password and recv[1] != api_password:
                            self.quit('API', api=1)
                            break
                        api_func(self, localServer, parsed)
                        self.quit('API', api=1)
                        return

                #print('ik ga zo slaaaaaapen maar jij bent ernie?')
                if type(self).__name__ == 'User' and command != 'nick' and command != 'user' and command != 'pong' and command != 'cap' and command != 'starttls' and command != 'webirc' and not self.registered:
                    return self.sendraw(451, 'You have not registered')
                if command == 'pong':
                    if self in self.server.pings:
                        ping = recv.split()[1]
                        if ping.startswith(':'):
                            ping = ping[1:]
                        if self.server.pings[self] == ping:
                            del self.server.pings[self]
                            self.validping = True
                            if self.ident != '' and self.nickname != '*' and (self.cap_end or not self.sends_cap):
                                self.welcome()
                        else:
                            return self.quit('Unauthorized connection')

                try:
                    cmd = importlib.import_module('cmds.cmd_'+command.lower())
                    getattr(cmd, 'cmd_'+command.upper())(self, localServer, parsed)
                    continue
                except ImportError:
                    try:
                        alias = localServer.conf['aliases']
                        if alias[command.lower()]['type'] == 'services':
                            service = list(filter(lambda u: u.nickname == alias[command.lower()]['target'] and 'services' in localServer.conf['settings'] and u.server.hostname == localServer.conf['settings']['services'], localServer.users))
                            if not service:
                                return self.sendraw(440, ':Services are currently down. Please try again later.')
                        data = '{} :{}'.format(alias[command.lower()]['target'], ' '.join(recv.split()[1:]))
                        self.handle('PRIVMSG', data)
                        continue
                    except KeyError:
                        pass
                false_cmd = True

                ### pre_command hook.
                allow = 1
                for callable in [callable for callable in self.server.hooks if callable[0].lower() == 'pre_command' and callable[1].lower() == command.lower()]:
                    try:
                        allow = callable[2](self, localServer, parsed)
                    except Exception as ex:
                        logging.exception(ex)
                if not allow and allow is not None:
                    continue

                for callable in [callable for callable in localServer.commands if callable[0].lower() == command.lower()]:
                    try:
                        got_params = len(parsed) - 1
                        req_params = callable[2]
                        req_modes = callable[3]
                        req_flags = callable[4]
                        req_class = callable[5]
                        module = callable[6]
                        if type(self).__name__ != req_class:
                            if req_class == 'Server':
                                return self.sendraw(487, ':{} is a server only command'.format(command.upper()))
                        if got_params < req_params:
                            return self.sendraw(461, ':{} Not enough parameters. Required: {}'.format(command.upper(), req_params))
                    except Exception as ex:
                        logging.exception(ex)

                    if req_modes:
                        req_modes = ' '.join(req_modes)
                        if 'o' in req_modes and 'o' not in self.modes:
                            return self.sendraw(481, ':Permission denied - You are not an IRC Operator')
                        forbid = set(req_modes).difference(set(self.modes))
                        if forbid:
                            return self.sendraw(481, ':Permission denied - Required mode not set')
                    forbid = True
                    if req_flags:
                        for flag in req_flags:
                            if '|' in flag:
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
                        callable[1](self, localServer, parsed)
                    except Exception as ex:
                        logging.exception(ex)
                if false_cmd:
                    self.sendraw(421, '{} :Unknown command'.format(command.upper()))

        except Exception as ex:
            logging.exception(ex)

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

    def _send(self, data):
        if not hasattr(self, 'socket'):
            logging.debug('Socket {} got sent flashed out.'.format(self))
            return
        if self.socket:
            self.sendbuffer += data + '\r\n'
            if self.server.use_poll:
                logging.debug('Flag for {} set to READ_WRITE (_send())'.format(self))
                self.server.pollerObject.modify(self.socket, READ_WRITE)

    def send(self, command, data):
        self._send(':{} {} {} {}'.format(self.server.hostname, command, self.nickname, data))

    def sendraw(self, numeric, data):
        self.send(str(numeric).rjust(3, '0'), data)

    def broadcast(self, users, data, source=None):
        if source:
            if type(source).__name__ == 'Server':
                source = source.hostname
            else:
                source.flood_penalty += 10000
                source = source.fullmask()
        else:
            source = self.fullmask()
            self.flood_penalty += 10000

        for user in users:
            user._send(':{} {}'.format(source, data))

    def setinfo(self, info, t='', source=None):
        try:
            if not info or not type:
                return
            if not source:
                return logging.error('No source provided in setinfo()!')
            if type(source) == str or type(source).__name__ != 'Server':
                return logging.error('Wrong source type provided in setinfo(): {}'.format(source))
            if t not in ['host', 'ident']:
                return logging.error('Incorrect type received in setinfo(): {}'.format(t))
            valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
            for c in str(info):
                if c.lower() not in valid:
                    info = info.replace(c, '')
            if not info:
                return
            updated = []
            if self.registered:
                for user in self.localServer.users:
                    for user in [user for user in self.localServer.users if 'chghost' in user.caplist and user not in updated and user.socket]:
                        common_chan = list(filter(lambda c: user in c.users and self in c.users, self.localServer.channels))
                        if not common_chan:
                            continue
                        user._send(':{} CHGHOST {} {}'.format(self.fullmask(), info if t == 'ident' else self.ident, info if t == 'host' else self.cloakhost))
                        updated.append(user)
                data = ':{} {} {}'.format(self.uid, 'SETHOST' if t == 'host' else 'SETIDENT', info)
                self.localServer.new_sync(self.localServer, source, data)
            if t == 'host':
                self.cloakhost = info
            elif t == 'ident':
                self.ident = info
        except Exception as ex:
            logging.exception(ex)

    def welcome(self):
        if not self.registered:
            for callable in [callable for callable in self.server.hooks if callable[0].lower() == 'pre_local_connect']:
                try:
                    callable[2](self, self.server)
                except Exception as ex:
                    logging.exception(ex)
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
                return self.quit('You are not authorized to connect to this server')

            totalClasses = list(filter(lambda u: u.registered and u.server == self.server and u.cls == self.cls, self.server.users))
            if len(totalClasses) > int(self.server.conf['class'][self.cls]['max']):
                return self.quit('Maximum connections for this class reached')

            clones = list(filter(lambda u: u.registered and u.socket and u.ip == self.ip, self.server.users))
            if len(clones) > int(self.server.conf['allow'][self.cls]['maxperip']):
                return self.quit('Maximum connections from your IP')

            current_lusers = len([user for user in self.server.users if user.server == self.server])
            if current_lusers > self.server.maxusers:
                self.server.maxusers = current_lusers

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

            if self.ssl and hasattr(self.socket, 'cipher'):
                self.send('NOTICE', ':*** You are connected to {} with {}-{}'.format(self.server.hostname, self.socket.version(), self.socket.cipher()[0]))
            msg = '*** Client connecting: {} ({}@{}) {{{}}} [{}{}]'.format(self.nickname, self.ident, self.hostname, self.cls, 'secure' if self.ssl else 'plain', ' '+self.socket.cipher()[0] if self.ssl else '')
            self.server.snotice('c', msg)

            binip = IPtoBase64(self.ip)
            data = '{} {} {} {} {} {} 0 +{} {} {} {} :{}'.format(self.nickname, self.server.hopcount, self.signon, self.ident, self.hostname, self.uid, self.modes, self.cloakhost, self.cloakhost, binip, self.realname)
            self.server.new_sync(self.server, self.server, ':{} UID {}'.format(self.server.sid, data))

            self.registered = True
            self.handle('lusers')
            self.handle('motd')
            for callable in [callable for callable in self.server.hooks if callable[0].lower() == 'welcome']:
                try:
                    callable[2](self, self.server)
                except Exception as ex:
                    logging.exception(ex)
            if self.fingerprint:
                self.send('NOTICE', ':*** Your SSL fingerprint is {}'.format(self.fingerprint))
                data = 'MD client {} certfp :{}'.format(self.uid, self.fingerprint)
                self.server.new_sync(self.server, self.server, ':{} {}'.format(self.server.sid, data))

            modes = []
            for mode in self.server.conf['settings']['modesonconnect']:
                if mode in self.server.user_modes and mode not in 'oqrzS':
                    modes.append(mode)
            if self.ssl and hasattr(self.socket, 'cipher'):
                modes.append('z')
            if len(modes) > 0:
                p = {'override': True}
                self.handle('mode', '{} +{}'.format(self.nickname, ''.join(modes)), params=p)

            watch_notify = [user for user in self.server.users if self.nickname.lower() in [x.lower() for x in user.watchlist]]
            for user in watch_notify:
                user.sendraw(600, '{} {} {} {} :logged online'.format(self.nickname, self.ident, self.cloakhost, self.signon))

            for callable in [callable for callable in self.server.hooks if callable[0].lower() == 'local_connect']:
                try:
                    callable[2](self, self.server)
                except Exception as ex:
                    logging.exception(ex)

        gc.collect()

    def __repr__(self):
        return "<User '{}:{}'>".format(self.fullmask(), self.server.hostname)

    def fileno(self):
        return self.socket.fileno()

    def fullmask(self):
        if not hasattr(self, 'cloakhost'):
            self.cloakhost = '*'
        return '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost)

    def fullrealhost(self):
        host = self.hostname if self.hostname else self.ip
        return '{}!{}@{}'.format(self.nickname, self.ident if self.ident != '' else '*', host)

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

    def ocheck(self, mode, flag):
        localServer = self.server if self.socket else self.localServer
        if (mode in self.modes and flag in self.operflags) or self.server.hostname.lower() in set(localServer.conf['settings']['ulines']):
            return True
        return False

    def quit(self, reason, error=True, banmsg=None, kill=False, silent=False, api=False): ### Why source?
        try:
            if not hasattr(self, 'socket'):
                self.socket = None
            self.recvbuffer = ''
            localServer = self.localServer if not self.socket else self.server
            sourceServer = self.server if (self.server.socket or self.server == localServer) else self.server.uplink
            if self.registered:
                logging.debug('User {} quit. Uplink source: {}'.format(self.nickname, sourceServer))
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'pre_local_quit']:
                try:
                    callable[2](self, localServer)
                except Exception as ex:
                    logging.exception(ex)

            if banmsg:
                localServer.notice(self, '*** You are banned from this server: {}'.format(banmsg))

            if int(time.time()) - self.signon < 300 and self.registered and not error and self.socket:
                reason = str(localServer.conf['settings']['quitprefix']).strip()
                if reason.endswith(':'):
                    reason = reason[:-1]
                reason += ': '+self.nickname

            if self.socket and reason and not api:
                self._send('ERROR :Closing link: [{}] ({})'.format(self.hostname, reason))

            while self.sendbuffer:
                #logging.info('User {} has sendbuffer remaining: {}'.format(self, self.sendbuffer.rstrip()))
                try:
                    sent = self.socket.send(bytes(self.sendbuffer + '\n', 'utf-8'))
                    self.sendbuffer = self.sendbuffer[sent:]
                except:
                    break

            if self in localServer.pings:
                del localServer.pings[self]
                #logging.debug('Removed {} from server PING check'.format(self))

            if self.registered and (self.server == localServer or self.server.eos):
                if reason and not kill:
                    skip = [sourceServer]
                    for server in [server for server in localServer.servers if hasattr(server, 'protoctl') and 'NOQUIT' in server.protoctl and not server.eos]:
                        skip.append(server)
                    localServer.new_sync(localServer, skip, ':{} QUIT :{}'.format(self.uid, reason))

                if self.socket and reason and not silent:
                    localServer.snotice('c', '*** Client exiting: {} ({}@{}) ({})'.format(self.nickname, self.ident, self.hostname, reason))

            for channel in [channel for channel in self.channels if 'j' in channel.modes]:
                self.handle('PART', '{}'.format(channel.name))
                continue

            ### Check module hooks for visible_in_channel()
            all_broadcast = [self]
            for channel in self.channels:
                for user in channel.users:
                    if user not in all_broadcast and user != self:
                        all_broadcast.append(user)
            inv_checked = 0
            for u in [u for u in all_broadcast if u != self]:
                visible = 0
                for channel in [chan for chan in self.channels if not visible]:
                    for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'visible_in_channel']:
                        try:
                            visible = callable[2](u, localServer, self, channel)
                            inv_checked = 1
                            #logging.debug('Is {} visible for {} on {}? :: {}'.format(self.nickname, u.nickname, channel.name, visible))
                        except Exception as ex:
                            logging.exception(ex)
                    if visible: ### Break out of the channels loop. No further checks are required.
                        break
                if not visible and inv_checked:
                    logging.debug('User {} is not allowed to see {} on any channel, not sending quit.'.format(u.nickname, self.nickname))
                    all_broadcast.remove(u)

            if self.nickname != '*' and self.ident != '' and reason:
                self.broadcast(all_broadcast, 'QUIT :{}'.format(reason))

            for channel in list(self.channels):
                channel.users.remove(self)
                channel.usermodes.pop(self)
                self.channels.remove(channel)
                if len(channel.users) == 0 and 'P' not in channel.modes:
                    localServer.channels.remove(channel)
                    del localServer.chan_params[channel]
                    for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'channel_destroy']:
                        try:
                            callable[2](self, localServer, channel)
                        except Exception as ex:
                            logging.exception(ex)

            watch_notify_offline = [user for user in localServer.users if self.nickname.lower() in [x.lower() for x in user.watchlist]]
            for user in watch_notify_offline:
                user.sendraw(601, '{} {} {} {} :logged offline'.format(self.nickname, self.ident, self.cloakhost, self.signon))

            if self in localServer.users:
                localServer.users.remove(self)

            if self.socket:
                if localServer.use_poll:
                    localServer.pollerObject.unregister(self.socket)
                try:
                    self.socket.shutdown(socket.SHUT_WR)
                except:
                    pass
                self.socket.close()

            hook = 'local_quit' if self.server == localServer else 'remote_quit'
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == hook]:
                try:
                    callable[2](self, localServer)
                except Exception as ex:
                    logging.exception(ex)

            gc.collect()
            del gc.garbage[:]

            if not localServer.forked:
                try:
                    logging.debug('Growth after self.quit() (if any):')
                    objgraph.show_growth(limit=20)
                except: # Prevent weird spam shit.
                    pass
            '''
            reflist = gc.get_referrers(self)
            if reflist:
                logging.debug('Found these references after quit:')
                for r in reflist:
                    logging.debug(r)
            else:
                logging.debug('Excellent, no more references!')
            '''
            #objgraph.show_refs([self], filename='refs.png')

            #for k, v in list(globals().items()):
            #    print("{} -- {}".format(k, v))

            #del self.socket
            del self

        except Exception as ex:
            logging.exception(ex)

    def handle(self, command, data=None, params=None):
        recv = '{} {}'.format(command, data if data else '')
        parsed = self.parse_command(recv)
        command = command.split()[0].lower()
        localServer = self.server if self.socket else self.origin
        for callable in [callable for callable in localServer.commands if callable[0].lower() == command]:
            got_params = len(parsed) - 1
            req_params = callable[2]
            req_modes = callable[3]
            req_flags = callable[4]
            if got_params < req_params:
                return self.sendraw(461, ':{} Not enough parameters. Required: {}'.format(command.upper(), req_params))
            if req_modes:
                if 'o' in req_modes and 'o' not in self.modes:
                    return self.sendraw(481, ':Permission denied - You are not an IRC Operator')
                forbid = set(req_modes).difference(set(self.modes))
                if forbid:
                    return self.sendraw(481, ':Permission denied - Required mode not set')
            if req_flags:
                if '|' in req_flags:
                    req_flags = req_flags.split('|')
                forbid = set(req_flags).difference(set(self.operflags))
                if forbid:
                    return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            try:
                if params:
                    callable[1](self, localServer, parsed, **params)
                else:
                    callable[1](self, localServer, parsed)
            except Exception as ex:
                logging.exception(ex)
