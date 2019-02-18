#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time

if sys.version_info[0] < 3:
    print('Python 2 is not supported.')
    sys.exit()

import signal

def handler(signum, frame):
    if signum == 17:
        return
    exit_handler()

try:
    import faulthandler
    faulthandler.enable()
except:
    pass
import gc
gc.enable()
import socket
import importlib
import platform
import argparse
import atexit
import psutil
import handle.handleConf
from handle.handleLink import Link as link
import handle.handleModules as Modules
#from OpenSSL import SSL

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
os.chdir(dir_path)
pidfile = dir_path+'/process.pid'

### Import classes.
from classes import user
User = user.User

from handle.functions import _print, match, is_sslport, update_support

def exit_handler():
    try:
        if os.path.isfile(pidfile):
            os.remove(pidfile)
    except Exception as ex:
        print('Failed to remove pidfile: {}'.format(ex))
    finally:
        sys.exit()

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
R2 = '\033[91m' # bright red
G = '\033[32m' # green
G2 = '\033[92m' # bright green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

#localServer = ''
#print('localServer set as: {}'.format(localServer))

class Channel:
    def __init__(self, name, params=None):
        self.name = name
        if not params:
            self.users = []
            self.modes = ''
            self.usermodes = {}
            self.topic = ""
            self.topic_author = ""
            self.topic_time = 0
            self.creation = int(time.time())
            self.limit = 0
            self.key = None
            self.redirect = None
            self.invites = {}
            self.bans = {}
            self.excepts = {}
            self.invex = {}

            self.temp_status = {}

    #def __del__(self):
        #pass
        #print('Channel {} closed'.format(self))

    def __repr__(self):
        return "<Channel '{}'>".format(self.name)

class Server:
    def __init__(self, conffile=None, forked=False, origin=None, serverLink=False, sock=None, is_ssl=False):
        self.ctime = int(time.time())
        self.syncDone = []
        self.replyPing = {}
        self.eos = False
        self.sendbuffer = ''
        self.hopcount = 0
        if not serverLink:
            try:
                self.forked = forked
                self.running = True
                self.listen_socks = {}
                self.bannedList = []
                self.rootdir = dir_path
                self.confdir = dir_path+'/conf/'
                self.modules_dir = dir_path+'/modules/'
                self.conffile = conffile
                self.commands = []
                self.modules = {}
                self.events = []
                self.user_modes = {}
                self.channel_modes = {}
                self.validconf = False
                self.datahandler = None
                self.localServer = self

                self.creationtime = int(time.time())

                self.versionnumber = '1.1'
                self.version = 'ProvisionIRCd-{}-beta'.format(self.versionnumber)
                self.hostinfo = 'Python {}'.format(sys.version.split('\n')[0].strip())

                self.caps = ['account-notify', 'away-notify', 'server-time', 'chghost', 'echo-message', 'tls', 'userhost-in-names', 'extended-join']
                self.socket = None
                self.introducedBy = None
                self.uplink = None
                self.users = []
                self.channels = []
                self.dnsblCache = {}
                self.hostcache = {}
                self.throttle = {}

                handle.handleConf.checkConf(self, None, self.confdir, self.conffile)

                if not self.validconf:
                    exit()
                    return

                self.hostname = self.conf['me']['server']
                self.name = self.conf['me']['name']
                self.sid = self.conf['me']['sid']

            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                _print(e, server=self)

            self.totalcons = 0
            self.gusers = []
            self.servers = []

            self.linkrequester = {}
            self.pendingLinks = []
            self.introducedTo = []

            self.maxusers = 0
            self.maxgusers = 0
            self.pings = {}

            update_support(self)
            return

        if serverLink:
            self.introducedBy = None
            self.uplink = None
            self.introducedTo = []
            self.sid = None
            self.netinfo = False

            self.linkAccept = False
            self.linkpass = None

            self.cls = None
            self.socket = sock
            self.is_ssl = is_ssl
            self.recvbuffer = ''
            self.sendbuffer = ''
            self.name = ''
            self.hostname = ''
            self.ping = int(time.time())
            self.lastPingSent = int(time.time())
            self.origin = origin
            self.localServer = origin
            self.localServer.servers.append(self)

    def fileno(self):
        return self.socket.fileno()

    def new_sync(self, localServer, skip, data):
        if type(skip) != list:
            skip = [skip]
        for t in [t for t in skip if type(t).__name__ != 'Server']:
            _print('{}HALT: wrong source type in new_sync(): {} with data: {}{}'.format(R2, t, data, W), server=self.localServer)
            return
        if data.split()[1] in ['UID', 'SID']:
            data = data.split()
            data = '{} {} {}'.format(' '.join(data[:3]), str(int(data[3]) + 1), ' '.join(data[4:]))
        for server in [server for server in localServer.servers if server.socket and server not in skip]:
            #print('New sync to {}: {}'.format(server, data))
            if not server.eos:
                _print('{}Not sycing to {} because it is in the middle of link procedure: {}{}'.format(R2, server, data, W), server=self.localServer)
                continue
            server._send(data)

    def syncToServers(self, localServer, sourceServers, data):
        if type(sourceServers) != list:
            sourceServers = [sourceServers]
        noSync = []
        noSync.append(localServer)
        noSync.extend(sourceServers)
        ### Do not sync back to USER server source based on UID.
        try:
            temp = list(filter(lambda u: u.uid == data.split()[0][1:] or u.nickname == data.split()[0][1:], localServer.users))
            tempserver = temp[0].server
            if tempserver not in set(noSync):
                _print('{}Adding {} tempserver to noSync (UID){}'.format(G, tempserver.hostname, W), server=localServer)
                noSync.append(tempserver)
            for s in localServer.servers:
                if tempserver.introducedBy == s and s not in noSync:
                    _print('{}Adding {} tempserver to noSync based on introducer (UID){}'.format(G, s.hostname, W), server=localServer)
                    noSync.append(s)

        except IndexError:
           pass
        try:
            ### Do not sync back to SERVER source based on SID.
            temp = list(filter(lambda s: s.sid == data.split()[0][1:], localServer.servers))
            tempserver = temp[0]
            if tempserver not in set(noSync):
                _print('{}Adding {} tempserver to noSync (SID){}'.format(G, tempserver.hostname, W), server=localServer)
                noSync.append(tempserver)
            ### Do not sync back to SERVER server source based on introducer (SID).
            for s in localServer.servers:
                if tempserver.introducedBy == s and s not in noSync:
                    _print('{}Adding {} tempserver to noSync based on introducer (SID){}'.format(G, s.hostname, W), server=localServer)
                    noSync.append(s)
        except IndexError:
            pass

        try:
            recv = data.split()
            isMsg = ['PRIVMSG', 'NOTICE']

            if recv[1] in set(isMsg):
                channel = [channel for channel in localServer.channels if channel.name.lower() == recv[2].lower()]
                user = [user for user in localServer.users if user.nickname.lower() == recv[2].lower() or user.uid == recv[2] and user.server not in noSync]

                if user and recv[1] in set(isMsg):
                    ### We have a private privmsg/notice, extra checks are necessary.
                    targetServer = user[0].server
                    if not targetServer.socket and targetServer not in sourceServers:
                        server = targetServer.introducedBy
                        _print('{}Cannot send directly to server. Syncing to {} :: {}{}'.format(P, server,server.hostname, W), server=localServer)
                            #pass
                        server._send(data)
                        return
            for server in (server for server in localServer.servers if server not in noSync and server.socket):
                if recv[1] in set(isMsg):
                    if channel:
                        users = [user for user in channel[0].users if user != self and user.server == server or user.server.introducedBy == server]
                        if not users:
                            #_print('{}No need to sync channel message to {}: no remote users on the channel{}'.format(P,server.hostname,W), server=localServer)
                            pass
                            continue
                    elif user:
                        if user[0].server != server:
                            #_print('{}No need to sync private message to {}: user {} not originating from remote server{}'.format(P,server.hostname,user[0],W), server=localServer)
                            pass
                            continue

                if recv[1] == 'UID':
                    ### Set hopcount.
                    user = list(filter(lambda u: u.nickname == recv[2], localServer.users))
                    if not user:
                        return
                    user = user[0]
                    if user.server != localServer:
                        hopcount = list(filter(lambda u: u.nickname == recv[2], localServer.users))[0].server.hopcount
                        recv[3] = str(hopcount)
                        #print('Hopcount set: {}'.format(hopcount))
                    data = ' '.join(recv)
                if server.hostname:
                    pass
                    #_print('{}Syncing to {}: {}{}'.format(P, server.hostname, data, W), server=localServer)
                if server.hostname:
                    server._send(data)
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
            _print(e)

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

    def _send(self, data, noSquit=False):
        if not data:
            return
        if self.socket:
            self.sendbuffer += data + '\r\n'
            ignore = ['PRIVMSG', 'NOTICE']
            try:
                if data.split()[0] != 'PONG' and data.split()[1] != 'PONG':
                    if len(data) > 1 and data.split()[1] not in set(ignore):
                        #pass
                        _print('{}{} <<<-- {}{}'.format(B, self.hostname if self.hostname != '' else self, data, W), server=self.localServer)
            except:
                pass

    def handle_recv(self):
        while self.recvbuffer.find("\n") != -1:
            try:
                recv = self.recvbuffer[:self.recvbuffer.find("\n")]
                self.recvbuffer = self.recvbuffer[self.recvbuffer.find("\n")+1:]
                recvNoStrip = recv.replace('\r', '').split(' ')
                recv = recv.split()
                if not recv:
                    self.recvbuffer = ''
                    continue
                if self.eos:
                    self.ping = time.time()
                raw = ' '.join(recv)
                command = recv[0].lower()
                prefix = command[:1]
                localServer = self.localServer
                try:
                    ignore = ['ping', 'pong', 'privmsg', 'notice']
                    #ignore = []
                    if command.lower() not in ignore and recv[1].lower() not in ignore:
                        _print('{}{} -->>> {}{}'.format(B, self.hostname if self.hostname != '' else self, ' '.join(recvNoStrip), W), server=localServer)
                        pass
                except Exception as ex:
                    pass
                    #print(ex)

                if prefix == '@':
                    # Server only.
                    for s in [s for s in localServer.servers if s != localServer and s != self and s.socket]:
                        s._send(raw)

                    source = command[1:]
                    serv = list(filter(lambda s: s.hostname == source or s.sid == source, localServer.servers))
                    if not serv:
                        continue
                    target = serv[0]
                    token = recv[1]
                    if token == 'AU':
                        ### Send PRIVMSG to all users with given usermode.
                        users = list(filter(lambda u: recv[2] in u.modes, localServer.users))
                        for user in users:
                            target.broadcast([user], 'PRIVMSG {} {}'.format(user.uid, ' '.join(recv[3:])))

                    elif token == 'Ss':
                        if serv[0] and not serv[0].eos and not serv[0].introducedBy.eos:
                            continue
                        ### Send NOTICE to all users with given snomask.
                        msg = ' '.join(recv[3:])[1:]
                        localServer.snotice(recv[2], msg, sync=False, source=serv[0])

                elif prefix == ':':
                    source = command[1:]
                    command = recv[1]
                    token = recv[1]
                    if command == 'BW' or command == 'BV' or command == 'SVSSNO':
                        source = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))
                        if not source:
                            continue
                        if 's' not in source[0].modes:
                            continue
                        snoset = None
                        for m in recv[2]:
                            if m in '+-':
                                snoset = m
                                continue
                            if snoset == '+' and 'm' not in source[0].snomasks:
                                source[0].snomasks += m
                            elif snoset == '-':source[0].snomasks = source[0].snomasks.replace(m, '')
                        if command == 'BW':
                            source[0]._send(':{} MODE +s :{}'.format(source[0].server.hostname, recv[2:]))
                            source[0].sendraw(8, 'Server notice mask (+{})'.format(source[0].snomasks))
                        localServer.new_sync(localServer, self, raw)
                        #localServer.syncToServers(localServer, source[0].server, raw)
                    try:
                        ### Old method -- use new method instead
                        cmd = importlib.import_module('cmds.cmd_'+command.lower())
                        getattr(cmd, 'cmd_'+command.upper())(self, localServer, recvNoStrip)
                        continue
                    except ImportError:
                        for callable in [callable for callable in localServer.commands if callable[0].lower() == command.lower()]:
                            ### (cmd, callable, params, req_modes, req_flags, module)
                            if command.lower() not in ['ping', 'pong']:
                                pass
                                #_print('handleLink calling: {} with {}'.format(callable, recv), server=localServer)
                            try:
                                callable[1](self, localServer, recvNoStrip)
                            except Exception as ex:
                                _print('Exception in module {}: {}'.format(callable[6], ex), server=localServer)
                        continue
                    except Exception as ex:
                        #pass
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                        _print(e, server=localServer)
                    continue

                else:
                    ### Old method -- use new method instead
                    '''
                    cmd = importlib.import_module('cmds.cmd_'+command.lower())
                    getattr(cmd, 'cmd_'+command.upper())(server, localServer, recvNoStrip)
                    '''
                    #_print('handleLink cmd handler 2 for cmd {}'.format(command), server=localServer)
                    for callable in [callable for callable in localServer.commands if callable[0].lower() == command.lower()]:
                        ### (command, function, params, req_modes, req_flags, req_class, module)
                        ### Do not add a return here, it will stop the recvbuffer read.
                        callable[1](self, localServer, recvNoStrip)

            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                _print(e, server=localServer)

        #if not self.linkThread:
        #    self.linkThread = link()

        #self.linkThread.handle_recv(self)

    def chlevel(self, channel):
        return 10000

    def ocheck(self, mode, flag):
        return True

    def __repr__(self):
        return "<Server '{}:{}'>".format('*' if not hasattr(self, 'hostname') else self.hostname, '*' if not hasattr(self, 'sid') else self.sid)

    def quit(self, reason, silent=False, error=False, noSquit=False, source=None):
        localServer = self.localServer
        _print('Server QUIT self: {}'.format(self), server=localServer)
        #print('Source: {}'.format(source))
        if self.uplink:
            _print('Server was uplinked to {}'.format(self.uplink), server=localServer)
        reason = reason[1:] if reason.startswith(':') else reason
        if self.hostname in localServer.linkRequests:
            del localServer.linkRequests[self.hostname]
        if self in localServer.introducedTo:
            localServer.introducedTo.remove(self)

        try:
            if self.hostname and self.eos:
                _print('{}Lost connection to remote server {}: {}{}'.format(R, self.hostname, reason, W), server=localServer)
                if not noSquit:
                    localServer.new_sync(localServer, localServer, ':{} SQUIT {} :{}'.format(localServer.sid, self.hostname, reason))
            self.eos = False

            if not silent and self.hostname and self.socket:
                localServer.snotice('s', '{} to server {}: {}'.format('Unable to connect' if not self.eos else 'Lost connection', self.hostname, reason), local=True)

            if self.hostname in set(localServer.pendingLinks):
                localServer.pendingLinks.remove(self.hostname)

            while self.sendbuffer:
                _print('Server {} has sendbuffer remaining: {}'.format(self, self.sendbuffer.rstrip()), server=localServer)
                ### Let's empty the sendbuffer manually.
                try:
                    sent = self.socket.send(bytes(self.sendbuffer + '\n', 'utf-8'))
                    self.sendbuffer = self.sendbuffer[sent:]
                except:
                    break

            ### Make a list of additional servers.
            additional_servers = [server for server in localServer.servers if server.introducedBy == self or server.uplink == self]
            for server in additional_servers:
                server.eos = False

            #_print('Removing all users from servers: {}'.format(additional_servers), server=localServer)
            ### Killing users with NoneType server.
            for [user for user in localServer.users if not user.server]:
                user.quit('Unknown connection')

            users = [user for user in localServer.users if user.server and (user.server == self or user.server in additional_servers or user.server.uplink == self)]
            for user in users:
                ### Netsplit between dev & link1
                server1 = self.hostname
                server2 = source.hostname if source else localServer.hostname
                user.quit('{} {}'.format(server1, server2), source=self)


            for server in additional_servers:
                server.quit('{} {}'.format(self.hostname, source.hostname if source else localServer.hostname))

            if self in localServer.servers:
                _print('Removing server {}'.format(self), server=localServer)
                localServer.servers.remove(self)

            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_WR)
                except:
                    self.socket.close()

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
            _print(e, server=localServer)

    def run(self):
        if self.forked:
            pid = os.fork()
            if pid:
                pid = str(pid)
                try:
                    print('PID [{}] forked to the background'.format(pid))
                    with open(pidfile, 'w') as file:
                        file.write(pid)
                except Exception as ex:
                    print('Could not write pidfile. Make sure you have write access: {}'.format(ex))
                    sys.exit()
                sys.exit()
                atexit.register(exit_handler)

        self.linkRequests = {}
        from handle.handleSockets import data_handler
        self.datahandler = data_handler(self)
        self.datahandler.start()
        #self.datahandler.join()
        return

    def handle(self, cmd, data, params=None):
        p = ' '.join([':'+self.sid, cmd.upper(), data]).split()
        try:
            handle = importlib.import_module('cmds.cmd_'+cmd.lower())
            getattr(handle, 'cmd_'+cmd.upper())(self, self.localServer, p)
            return
        except ImportError:
            for callable in [callable for callable in self.localServer.commands if callable[0].lower() == cmd.lower()]:
                ### (cmd, callable, params, req_modes, req_flags, module)
                _print('Calling {} with: {}'.format(callable, p))
                if params:
                    callable[1](self, self.localServer, p, **params)
                else:
                    callable[1](self, self.localServer, p)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
            _print(e, server=self.localServer)

    def broadcast(self, users, data, source=None):
        ### Source must be a class.
        if source:
            if type(source).__name__ == 'Server':
                source = source.hostname
            else:
                source = source.fullmask()
        else:
            source = self.hostname
        for user in users:
            user._send(':{} {}'.format(source, data))

    def notice(self, user, msg):
        user._send(':{} NOTICE {} :{}'.format(self.hostname, user.nickname, msg))

    def snotice(self, sno, msg, sync=True, source=None, local=False):
        localServer = self.localServer
        try:
            if sno:
                users = list(filter(lambda u:'o' in u.modes and sno in u.snomasks, localServer.users))

            for user in set(users):
                try:
                    if sno in localServer.conf['opers'][user.operaccount]['ignore']['snomask']:
                        for m in localServer.conf['opers'][user.operaccount]['ignore']['snomask'][sno]:
                            for word in msg.split():
                                if match(m, word) and user in users and user.server == localServer:
                                    users.remove(user)
                                    break
                except Exception as ex:
                    pass

            for user in [user for user in users if user.socket]:
                if source:
                    displaySource = source.hostname
                else:
                    displaySource = self.hostname
                user._send(':{} NOTICE {} :{}'.format(displaySource, user.nickname, msg))

            localsno = ['j', 't', 'G'] ### I removed 's' from localsno. See you soon.
            if sno not in set(localsno) and sync and not local:
                if sno == 'c':
                    sno = 'C'
                data = '@{} Ss {} :{}'.format(self.hostname, sno, msg)
                localServer.new_sync(localServer, self, data)
                #localServer.syncToServers(localServer, self, data)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
            _print(e, server=localServer)

    def listenToPort(self, port, type):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("", port))
            self.sock.settimeout(1)
            self.sock.listen(5)
            print('Server listening on port {} :: {} ({})'.format(port, 'SSL' if is_sslport(self, port) else 'insecure', type))
            return self.sock
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
            print(e)
            print('Another instance running?')
            sys.exit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='IRCd.')
    parser.add_argument('-c', '--conf', help='Conf file.')
    parser.add_argument('--nofork', help='No fork.',action='store_true')
    parser.add_argument('--mkpasswd', help='Generate bcrypt password')
    args = parser.parse_args()

    '''
    signals = {
            signal.SIGABRT: 'signal.SIGABRT',
            signal.SIGALRM: 'signal.SIGALRM',
            signal.SIGBUS: 'signal.SIGBUS',
            signal.SIGCHLD: 'signal.SIGCHLD',
            signal.SIGCONT: 'signal.SIGCONT',
            signal.SIGFPE: 'signal.SIGFPE',
            signal.SIGHUP: 'signal.SIGHUP',
            signal.SIGILL: 'signal.SIGILL',
            signal.SIGINT: 'signal.SIGINT',
            signal.SIGPIPE: 'signal.SIGPIPE',
            signal.SIGPOLL: 'signal.SIGPOLL',
            signal.SIGPROF: 'signal.SIGPROF',
            signal.SIGQUIT: 'signal.SIGQUIT',
            signal.SIGSEGV: 'signal.SIGSEGV',
            signal.SIGSYS: 'signal.SIGSYS',
            signal.SIGTERM: 'signal.SIGTERM',
            signal.SIGTRAP: 'signal.SIGTRAP',
            signal.SIGTSTP: 'signal.SIGTSTP',
            signal.SIGTTIN: 'signal.SIGTTIN',
            signal.SIGTTOU: 'signal.SIGTTOU',
            signal.SIGURG: 'signal.SIGURG',
            signal.SIGUSR1: 'signal.SIGUSR1',
            signal.SIGUSR2: 'signal.SIGUSR2',
            signal.SIGVTALRM: 'signal.SIGVTALRM',
            signal.SIGXCPU: 'signal.SIGXCPU',
            signal.SIGXFSZ: 'signal.SIGXFSZ',
            }

    for num in signals:
        #print('Checking {}'.format(signals[num]))
        signal.signal(num, handler)
    '''
    global conffile
    if not args.conf:
        conffile = 'ircd.conf'
    else:
        conffile = args.conf
    fork = not args.nofork
    if args.mkpasswd:
        try:
            import bcrypt
        except ImportError:
            print("Could not import required 'bcrypt' module. You can install it with pip")
            sys.exit()

        hashed = bcrypt.hashpw(args.mkpasswd.encode('utf-8'),bcrypt.gensalt(15)).decode('utf-8')
        print('Your salted password: {}'.format(hashed))
    else:
        version = '{}{}'.format(sys.version_info[0], sys.version_info[1])
        if int(version) < 36:
            print('Python version 3.6 or higher is recommended due to better memory management.')
            time.sleep(1)
        S = Server(conffile=conffile, forked=fork)
        S.run()
