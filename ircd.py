#!/usr/bin/env python
# -*- coding: utf-8 -*-
import faulthandler
faulthandler.enable()
import socket
import importlib
import time
import os
import sys
import platform
import argparse
import gc
import atexit
import psutil
import gc
gc.enable()
#from multiprocessing import Process
import handle.handleConf
from handle.handleLink import Link as link
import handle.handleModules as Modules

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
os.chdir(dir_path)
pidfile = dir_path+'/process.pid'

### Import classes.
from classes import user
User = user.User

from handle.functions import _print, match, is_sslport

from cmds import cmd_tkl
TKL = cmd_tkl.TKL()

def exit_handler():
    try:
        #print('Removing {}'.format(pidfile))
        os.remove(pidfile)
    except:
        pass

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
G = '\033[32m' # green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

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
            self.chmodef = {}
            self.messageQueue = {}
            self.joinQueue = {}
            self.temp_status = {}

    def __del__(self):
        pass
        #print('Channel {} closed'.format(self))

    def __repr__(self):
        return "<Channel '{}'>".format(self.name)

class Server(socket.socket):
    def __init__(self, conffile=None, forked=False, origin=None, serverLink=False, sock=None):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.ctime = int(time.time())
        self.syncDone = []
        self.replyPing = {}
        self.eos = False

        if not serverLink:
            try:
                self.forked = forked
                #self.setblocking(0)
                self.running = True
                self.listenSocks = []
                self.bannedList = []
                self.rootdir = dir_path
                self.confdir = dir_path+'/conf/'
                self.modules_dir = dir_path+'/modules/'
                self.conffile = conffile
                self.commands = []
                self.modules = {}
                self.events = []
                self.privilege = []
                self.module_channel_modes = []
                self.module_user_modes = []
                self.validconf = False
                ### Hooking core commands
                Modules.LoadCommands(self)
                c = handle.handleConf.checkConf(self, None, self.confdir, self.conffile)
                c.start()
                c.join()
                if not self.validconf:
                    exit()
                    return
                self.hostname = self.conf['me']['server']
                self.name = self.conf['me']['name']
                self.sid = self.conf['me']['sid']
                self.socket = None
                self.introducedBy = None

            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                print(e)

            self.totalcons = 0
            self.users = []
            self.gusers = []
            self.servers = []
            self.whowas = {}

            self.linkrequester = {}
            self.pendingLinks = []
            self.introducedTo = []

            self.maxusers = 0
            self.maxgusers = 0
            self.channels = []
            self.pings = {}
            self.throttle = {}
            self.nickflood = {}

            self.hostcache = {}
            self.tkl = {}
            self.dnsblCache = {}

            self.creationtime = int(time.time())

            self.versionnumber = '1.1'
            self.version = 'ProvisionIRCd-{}'.format(self.versionnumber)
            self.hostinfo = 'Python {}'.format(sys.version.split('\n')[0].strip())
            self.chmodes = 'beI,kLf,l,imnjprstzCNOQRTV'
            self.chmodef = 'jm'
            self.chstatus = 'yqaohv'
            self.umodes = 'ioxqrsczHSW^'

            chmodes = ''.join(self.chmodes.split(',')[3])
            for m in self.module_channel_modes:
                if m[0] not in self.chmodes:
                    chmodes += m[0]
            chmodes = ''.join(sorted(set(chmodes)))
            self.allchmodes = ''.join(self.chmodes.split(',')[0])+','+''.join(self.chmodes.split(',')[1])+','+''.join(self.chmodes.split(',')[2])+','+chmodes

            for m in self.module_user_modes:
                if m[0] not in self.umodes:
                    self.umodes += m[0]
            self.umodes = ''.join(sorted(set(self.umodes)))

            self.snomasks = 'cdfjkostwzCFGNQS'

            self.maxtargets = 20
            self.maxmodes = 12
            self.maxwatch = 256
            self.chantypes = '#+&'
            self.chprefix = '(yqaohv)!~&@%+'
            self.nicklen = 33
            self.chanlen = 33
            self.topiclen = 307
            self.kicklen = 307
            self.awaylen = 160
            self.maxlist = {}
            self.maxlist['b'] = 200
            self.maxlist['e'] = 200
            self.maxlist['I'] = 200
            self.extBans = 'TCt'
            self.raw005 = 'MAXTARGETS={} WATCH={} WATCHOPTS=A MODES={} CHANTYPES={} PREFIX={} CHANMODES={} MAXLIST=b:{},e:{},I:{} NICKLEN={} CHANNELLEN={} TOPICLEN={} KICKLEN={} AWAYLEN={} EXTBAN=~,{} NETWORK={}'\
            .format(self.maxtargets, self.maxwatch, self.maxmodes, self.chantypes, self.chprefix, self.allchmodes, self.maxlist['b'], self.maxlist['e'], self.maxlist['I'],\
            self.nicklen, self.chanlen, self.topiclen, self.kicklen, self.awaylen, self.extBans, self.name)

        if serverLink:
            self.introducedBy = None
            self.allowUidSjoinSync = False
            self.introducedTo = []
            self.hopcount = 0
            self.sid = None
            self.netinfo = False
            ### Temporary store sync data to send after server introductions.
            self.tempSync = []
            ### Store servers to which I've already synced.

            self.linkAccept = False
            self.linkpass = None

            self.linkThread = None
            self.cls = None
            self.socket = sock
            if self.socket:
                self.socket.setblocking(0)
            self.recvbuffer = ''
            self.sendbuffer = ''
            self.name = ''
            self.hostname = ''
            self.ping = int(time.time())
            self.lastPingSent = int(time.time())
            self.origin = origin
            self.origin.servers.append(self)

    def syncToServers(self, localServer, sourceServer, data):
        noSync = []
        noSync.append(localServer)
        if sourceServer not in set(noSync):
            noSync.append(sourceServer)
        ### Do not sync back to USER server source based on UID.
        try:
            temp = list(filter(lambda u: u.uid == data.split()[0][1:] or u.nickname == data.split()[0][1:], localServer.users))
            tempserver = temp[0].server
            if tempserver not in set(noSync):
                if not localServer.forked:
                    print('{}Adding {} tempserver to noSync (UID){}'.format(G, tempserver.hostname, W))
                noSync.append(tempserver)
            for s in localServer.servers:
                if tempserver.introducedBy == s and s not in set(noSync):
                    if not localServer.forked:
                        print('{}Adding {} tempserver to noSync based on introducer (UID){}'.format(G, s.hostname, W))
                    noSync.append(s)
        except IndexError:
           pass
        try:
            ### Do not sync back to SERVER source based on SID.
            temp = list(filter(lambda s: s.sid == data.split()[0][1:], localServer.servers))
            tempserver = temp[0]
            if tempserver not in set(noSync):
                if not localServer.forked:
                    print('{}Adding {} tempserver to noSync (SID){}'.format(G, tempserver.hostname, W))
                noSync.append(tempserver)
            ### Do not sync back to SERVER server source based on introducer (SID).
            for s in localServer.servers:
                if tempserver.introducedBy == s and s not in set(noSync):
                    if not localServer.forked:
                        print('{}Adding {} tempserver to noSync based on introducer (SID){}'.format(G, s.hostname, W))
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
                    if not targetServer.socket and targetServer != sourceServer:
                        server = targetServer.introducedBy
                        if not localServer.forked:
                            print('{}Cannot send directly to server. Syncing to {} :: {}{}'.format(P, server,server.hostname, W))
                            #pass
                        server._send(data)
                        return
            for server in (server for server in localServer.servers if server not in noSync and server.socket):
                if recv[1] in set(isMsg):
                    if channel:
                        users = [user for user in channel[0].users if user != self and user.server == server or user.server.introducedBy == server]
                        if not users:
                            if not localServer.forked:
                                #print('{}No need to sync channel message to {}: no remote users on the channel{}'.format(P,server.hostname,W))
                                pass
                            continue
                    elif user:
                        if user[0].server != server:
                            if not localServer.forked:
                                #print('{}No need to sync private message to {}: user {} not originating from remote server{}'.format(P,server.hostname,user[0],W))
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
                if not localServer.forked and server.hostname:
                    #pass
                    print('{}Syncing to {}: {}{}'.format(P, server.hostname,data, W))
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
            self.socket.send(bytes('{}\r\n'.format(data), 'utf-8'))
            ignore = ['PRIVMSG', 'NOTICE']
            try:
                if data.split()[0] != 'PONG' and data.split()[1] != 'PONG':
                    if len(data) > 1 and data.split()[1] not in set(ignore):
                        pass
                        #_print('{}{} <<<-- {}{}'.format(B, self.hostname if self.hostname != '' else self, data, W), server=self.origin)
            except:
                pass

    def handle_recv(self):
        if not self.linkThread:
            self.linkThread = link()

        self.linkThread.handle_recv(self)

    def chlevel(self,channel):
        return 10000

    def ocheck(self,mode,flag):
        return True

    def __repr__(self):
        return "<Server '{}:{}'>".format(self.hostname, self.sid)

    def quit(self, reason, silent=False, error=False, noSquit=False):

        localServer = self.origin
        reason = reason[1:] if reason.startswith(':') else reason
        if self.hostname in localServer.linkRequests:
            del localServer.linkRequests[self.hostname]

        try:
            if self.hostname and self.eos:
                if not localServer.forked:
                    print('{}Lost connection to remote server {}: {}{}'.format(R, self.hostname, reason, W))
                if not noSquit:
                    for s in localServer.servers:
                        try:
                            s._send(':{} SQUIT {} :{}'.format(localServer.hostname, self.hostname, reason))
                        except:
                            pass

            if self in set(localServer.servers):
                localServer.servers.remove(self)

            if not silent and self.hostname:
                localServer.snotice('s', '{} to server {}: {}'.format('Unable to connect' if not self.eos else 'Lost connection', self.hostname, reason))
                self.eos = False

            if self.hostname in set(localServer.pendingLinks):
                localServer.pendingLinks.remove(self.hostname)

            if error and self.socket:
                ip, port = self.socket.getsockname()
                self.socket.send(bytes('ERROR :Closing link: [{}] ({})\r\n'.format(ip, reason),'utf-8'))

            ### Make a list of additional servers.
            servers = list(filter(lambda s: s.introducedBy == self, localServer.servers))
            users = (user for user in localServer.users if user.server and (user.server.hostname == self.hostname and user.server != localServer) or user.server in servers)
            for user in users:
                user.quit('{} {}'.format(localServer.hostname, user.server.introducedBy.hostname if user.server.introducedBy else user.server.hostname))
                #user.quit('{} {}'.format(user.server.hostname, user.server.introducedBy.hostname if user.server.introducedBy else localServer.hostname))
            for s in servers:
                if s.hostname in localServer.linkRequests:
                    del localServer.linkRequests[s.hostname]
                localServer.servers.remove(s)
                if s in set(localServer.introducedTo):
                    localServer.introducedTo.remove(s)

            if self.socket:
                self.socket.close()

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
            _print(e)

    def run(self):
        for p in self.conf['listen']:
            if 'clients' in set(self.conf['listen'][p]['options']):
                try:
                    listen_socks[self.listenToPort(int(p),'clients')] = 'clients'
                except Exception as ex:
                    print('Unable to listen on port {}: {}'.format(p, ex))

            elif 'servers' in set(self.conf['listen'][p]['options']):
                try:
                    listen_socks[self.listenToPort(int(p),'servers')] = 'servers'
                except Exception as ex:
                    print('Unable to listen on port {}: {}'.format(p, ex))

        from handle.handleData import handleData
        handleData(self, listen_socks)
        return

    def handle(self, cmd, data):
        try:
            localServer = self if not self.socket else self.origin
            #_print('Server handle localServer set: {}'.format(localServer),server=localServer)
            handle = importlib.import_module('cmds.cmd_'+cmd.lower())
            p = ' '.join([cmd.upper(),data]).split()
            #_print('Server handle data: {} {}'.format(cmd,p),server=localServer)
            getattr(handle, 'cmd_'+cmd.upper())(self, localServer, p)
            return
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
            print(e)

    def broadcast(self, users, data, source=None):
        ### Source must be a class.
        if source:
            if type(source).__name__ == 'Server':
                source = source.hostname
            else:
                source = source.fullmask()
        else:
            source = self.hostname
        #print('(server) Broadcast source: {}'.format(source))
        for user in users:
            user._send(':{} {}'.format(source, data))

    def snotice(self, sno, msg, sync=True, source=None, local=False):
        localServer = self if not self.socket else self.origin
        try:
            if sno:
                users = list(filter(lambda u:sno in u.snomasks and 'o' in u.modes, localServer.users))

            for user in list(users):
                try:
                    if sno in localServer.conf['opers'][user.operaccount]['ignore']['snomask']:
                        for m in localServer.conf['opers'][user.operaccount]['ignore']['snomask'][sno]:
                            for word in msg.split():
                                if match(m, word) and user in users and user.server == localServer:
                                    users.remove(user)
                                    break
                except Exception as ex:
                    pass

            for user in users:
                if user.socket:
                    if source:
                        displaySource = source.hostname
                    else:
                        displaySource = user.server.hostname
                    user._send(':{} NOTICE {} :{}'.format(displaySource, user.nickname, msg))
            localsno = ['s', 'j', 't', 'G']
            if sno not in set(localsno) and sync:
                if sno == 'c':
                    sno = 'C'
                data = '@{} Ss {} :{}'.format(self.hostname, sno, msg)
                localServer.syncToServers(localServer, self, data)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
            _print(e)

    def listenToPort(self, port, type):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("",port))
            self.sock.settimeout(0.1)
            self.sock.listen(5)
            self.sock.setblocking(0)
            print('Server listening on port {} :: {} ({})'.format(port, 'SSL' if is_sslport(self,port) else 'insecure', type))
            self.listenSocks.append(self.sock)
            return self.sock
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
            print(e)
            print('Another instance running?')
            sys.exit()

def startServer(conffile, forked):
    atexit.register(exit_handler)
    S = Server(conffile=conffile, forked=forked)
    S.run()

def boot(conffile=None, forking=False):
    if conffile is None:
        return
    conffile = conffile
    if platform.system() == 'Linux':
        if forking:
            pid = os.fork()
            if pid:
                print('PID [{}] forked to the background'.format(pid))
                with open(pidfile,'w') as file:
                    file.write(str(pid))
                sys.exit()
        startServer(conffile, forked=forking)
    if platform.system() == 'Windows':
        startServer(conffile, forked=forking)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='IRCd.')
    parser.add_argument('-c', '--conf', help='Conf file.')
    parser.add_argument('--nofork', help='No fork.',action='store_true')
    parser.add_argument('--mkpasswd', help='Generate bcrypt password')
    args = parser.parse_args()
    #global listen_socks
    listen_socks = {}
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
            print("Could not import 'bcrypt' module. You can install it with pip")
        hashed = bcrypt.hashpw(args.mkpasswd.encode('utf-8'),bcrypt.gensalt(10)).decode('utf-8')
        print('Your salted password: {}'.format(hashed))
    else:
        boot(conffile, forking=fork)
