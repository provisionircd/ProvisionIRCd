#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import ssl

if sys.version_info[0] < 3:
    print('Python 2 is not supported.')
    sys.exit()

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
import handle.handleConf
from handle.handleLink import Link as link
import handle.handleModules as Modules
from collections import OrderedDict
import select
import objgraph

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
os.chdir(dir_path)
pidfile = dir_path+'/process.pid'

### Import classes.
from classes import user
User = user.User

from handle.functions import _print, match, is_sslport, update_support, logging

def exit_handler():
    try:
        if os.path.isfile(pidfile):
            os.remove(pidfile)
    except Exception as ex:
        print('Failed to remove pidfile: {}'.format(ex))
    finally:
        sys.exit()

W = '\033[0m'  # white (normal)
R2 = '\033[91m' # bright red
B = '\033[34m' # blue

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
            self.invites = {}
            self.bans = OrderedDict({})
            self.excepts = OrderedDict({})
            self.invex = OrderedDict({})
            self.temp_status = {}

    def __repr__(self):
        return "<Channel '{}'>".format(self.name)

READ_ONLY = (
    select.POLLIN |
    select.POLLPRI |
    select.POLLHUP |
    select.POLLERR
)
READ_WRITE = READ_ONLY | select.POLLOUT

class Server:
    def __init__(self, conffile=None, forked=False, origin=None, serverLink=False, sock=None, is_ssl=False):
        self.ctime = int(time.time())
        self.syncDone = []
        self.eos = False
        self.sendbuffer = ''
        self.hopcount = 0
        if not serverLink:
            try:
                self.forked = forked
                self.hostname = '*'
                from handle.functions import initlogging
                initlogging(self)
                self.running = 0
                self.listen_socks = {}
                self.bannedList = []
                self.rootdir = dir_path
                self.confdir = dir_path+'/conf/'
                self.modules_dir = dir_path+'/modules/'
                self.conffile = conffile
                self.commands = []
                self.api = []
                self.modules = {}
                self.events = []
                self.hooks = []
                self.user_modes = {}
                self.channel_modes = {}
                self.localServer = self
                self.linkRequests = {}
                self.sync_queue = {}
                self.creationtime = int(time.time())

                self.versionnumber = '1.4'
                self.version = 'ProvisionIRCd-{}'.format(self.versionnumber)
                self.hostinfo = 'Python {}'.format(sys.version.split('\n')[0].strip())

                ### Polling does not work.
                self.use_poll = 0 ### Polling does not work.
                self.pre_wrap = 0 ### Polling does not work. Also pre-wrapping may cause memleak? Not sure, needs checking. It will prevent you from reloading certs.
                if self.use_poll:
                    self.pollerObject = select.poll()
                    self.fd_to_socket = {}
                ### Polling does not work.

                self.socket = None
                self.introducedBy = None
                self.uplink = None
                self.users = []
                self.channels = []
                self.dnsblCache = {}
                self.hostcache = {}
                self.throttle = {}
                self.tkl = {}
                self.user_modes = {
                    "i": (0, "User does not show up in outside /who"),
                    "o": (2, "IRC Operator"),
                    "x": (0, "Hides real host with cloaked host"),
                    "q": (1, "Protected on all channels"),
                    "r": (2, "Identifies the nick as being logged in"),
                    "s": (1, "Can receive server notices"),
                    "z": (2, "User is using a secure connection"),
                    "B": (0, "Marks the client as a bot"),
                    "H": (1, "Hide IRCop status"),
                    "S": (2, "Marks the client as a network service"),
                }
                self.channel_modes = {
                ### +v = 1
                ### +h = 2
                ### +o = 3
                ### +a = 4
                ### +q = 5
                ### oper = 6
                ### server = 7
                            0: {
                                "b": (2, "Bans the given hostmask from the channel", "<nick!ident@host>"),
                                "e": (2, "Users matching an except can go through channel bans", "<nick!ident@host>"),
                                "I": (2, "Matching users can go through channel mode +i", "<nick!ident@host>"),
                                },
                            1: {
                                "k": (2, "User must give a key in order to join the channel", "<key>"),
                                "L": (5, "When the channel is full, redirect users to another channel (requires +l)", "<chan>"),
                                },
                            2: {
                                "l": (2, "Set a channel user limit", "[number]"),
                                },
                            3: {
                                "m": (2, "Moderated channel, need +v or higher to talk"),
                                "n": (2, "No outside messages allowed"),
                                "j": (3, "Quits appear as parts"),
                                "p": (3, "Private channel"),
                                "r": (7, "Channel is registered"),
                                "s": (3, "Channel is secret"),
                                "t": (3, "Only +h or higher can change topic"),
                                "z": (3, "Requires SSL to join the channel"),
                                "C": (2, "CTCPs are not allowed in the channel"),
                                "N": (4, "Nickchanges are not allowed in the channel"),
                                "O": (6, "Only IRCops can join"),
                                "P": (6, "Permanent channel"),
                                "Q": (4, "No kicks allowed"),
                                "R": (3, "You must be registered to join the channel"),
                                "T": (2, "Notices are not allowed in the channel"),
                                "V": (3, "Invite is not permitted on the channel"),
                                },
                        }
                self.core_chmodes = 'vhoaq'
                chmodes_string = ''
                for t in self.channel_modes:
                    for m in self.channel_modes[t]:
                        chmodes_string += m
                        if t > 0:
                            self.core_chmodes += m
                    chmodes_string += ','
                logging.info('Core modes set: {}'.format(self.core_chmodes))
                self.chmodes_string = chmodes_string[:-1]
                #self.snomasks = 'cdfjkostzCFGNQS'
                self.snomasks = {
                                "c": "Can read local connect/disconnect notices",
                                "d": "Can see DNSNL hits",
                                "f": "See flood alerts",
                                "k": "View kill notices",
                                "o": "See oper-up notices",
                                "s": "General server notices",
                                "t": "Trash notices (unimportant stuff)",
                                "C": "Can read global connect/disconnect notices",
                                "F": "View spamfilter matches",
                                "G": "View TKL usages",
                                "N": "Can see nick changes",
                                "Q": "View Q:line rejections",
                                "S": "Can see /sanick, /sajoin, and /sapart usage",
                                }

                self.chstatus = 'yqaohv'
                self.chprefix = OrderedDict(
                                    [
                                    ('y', '!'),
                                    ('q', '~'),
                                    ('a', '&'),
                                    ('o', '@'),
                                    ('h', '%'),
                                    ('v', '+')
                                    ])
                self.chprefix = OrderedDict(self.chprefix)
                chprefix_string = ''
                first = '('
                second = ''
                for key in self.chprefix:
                    first += key
                    second += self.chprefix[key]
                first += ')'
                self.chprefix_string = '{}{}'.format(first, second)
                self.parammodes = self.chstatus
                for x in range(0, 4):
                    for m in [m for m in self.channel_modes[x] if str(x) in '012' and m not in self.parammodes]:
                        self.parammodes += m
                self.chan_params = {}
                self.maxlist = {}
                self.maxlist['b'] = 500
                self.maxlist['e'] = 500
                self.maxlist['I'] = 500
                self.maxlist_string = 'b:{},e:{},I:{}'.format(self.maxlist['b'], self.maxlist['e'], self.maxlist['I'])
                self.servers = []

                validconf = handle.handleConf.checkConf(self, None, self.confdir, self.conffile)

                if not validconf:
                    exit()
                    return

                self.running = 1

            except Exception as ex:
                logging.exception(ex)
                exit()
                return

            self.totalcons = 0
            self.gusers = []

            self.linkrequester = {}
            self.pendingLinks = []
            self.introducedTo = []

            self.maxusers = 0
            self.maxgusers = 0
            self.pings = {}

            update_support(self)
            return

        if serverLink:
            self.localServer = origin
            self.socket = sock
            if self.localServer.use_poll:
                fd = self.fileno()
                self.localServer.pollerObject.register(self.socket, READ_WRITE)
                self.localServer.fd_to_socket[fd] = (self.socket, self)
                logging.debug('Added {} to fd dict with fd {}'.format(self, fd))
            self.creationtime = int(time.time())
            self.introducedBy = None
            self.uplink = None
            self.introducedTo = []
            self.sid = None
            self.netinfo = False
            self.linkAccept = False
            self.linkpass = None
            self.cls = None
            self.is_ssl = is_ssl
            self.recvbuffer = ''
            self.name = ''
            self.hostname = ''
            self.ping = int(time.time())
            self.lastPingSent = time.time() * 1000
            self.lag = int((time.time() * 1000) - self.lastPingSent)
            self.origin = origin
            self.localServer.servers.append(self)

    def __del__(self):
        pass
        #logging.debug('Server {} closed'.format(self))

    def fileno(self):
        return self.socket.fileno()

    def new_sync(self, localServer, skip, data, direct=None):
        try:
            if type(skip) != list:
                skip = [skip]
            for t in [t for t in skip if type(t).__name__ != 'Server']:
                logging.error('{}HALT: wrong source type in new_sync(): {} with data: {}{}'.format(R2, t, data, W))
                return
            if data.split()[1] in ['UID', 'SID']:
                data = data.split()
                data = '{} {} {}'.format(' '.join(data[:3]), str(int(data[3]) + 1), ' '.join(data[4:]))
            if direct: ### Private messages and notices.
                dest = direct if direct.socket else direct.uplink
                if direct.socket:
                    logging.info('Directly linked to us, no more hops needed.')
                else:
                    logging.info('Server has hopcount of {}, sending to {} first.'.format(direct.hopcount, direct.uplink))
                dest._send(data)
                return

            for server in [server for server in localServer.servers if server and server.socket and server not in skip]:
                if not server.eos:
                    if server not in localServer.sync_queue:
                        localServer.sync_queue[server] = []
                    localServer.sync_queue[server].append(data)
                    logging.info('{}Added to {} sync queue because they are not done syncing: {}{}'.format(R2, server, data, W))
                    continue
                server._send(data)
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
        try:
            if self.socket:
                self.sendbuffer += data + '\r\n'
                if self.localServer.use_poll:
                    logging.debug('Flag for {} set to READ_WRITE (_send())'.format(self))
                    self.localServer.pollerObject.modify(self.socket, READ_WRITE)
                ignore = ['PRIVMSG', 'NOTICE', 'PING', 'PONG']
                try:
                    if data.split()[0] not in ['PING', 'PONG']:
                        if len(data) > 1 and data.split()[1] not in ignore:
                            #pass
                            logging.info('{}{} <<<-- {}{}'.format(B, self.hostname if self.hostname != '' else self, data, W))
                except:
                    pass
        except Exception as ex:
            logging.exception(ex)

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
                raw = ' '.join(recv)
                command = recv[0].lower()
                prefix = command[:1]
                localServer = self.localServer
                try:
                    ignore = ['ping', 'pong', 'privmsg', 'notice']
                    #ignore = []
                    if command.lower() not in ignore and recv[1].lower() not in ignore:
                        logging.info('{}{} -->>> {}{}'.format(B, self.hostname if self.hostname != '' else self, ' '.join(recvNoStrip), W))
                        pass
                except Exception as ex:
                    pass

                missing_mods = []
                if recv[0].upper() == 'MODLIST':
                    try:
                        remote_modules
                    except:
                        remote_modules = []
                    remote_modules.extend(' '.join(recv[1:])[1:].split())
                    continue
                try:
                    if remote_modules:
                        local_modules = [m.__name__ for m in localServer.modules]
                        for m in [m for m in remote_modules if m not in local_modules]:
                            missing_mods.append(m)
                    if missing_mods:
                        string = ', '.join(missing_mods)
                        self._send(':{} ERROR :they are missing modules: {}'.format(localServer.sid, string))
                        self.quit('we are missing modules: {}'.format(string))
                        return
                except:
                    pass

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

                    for callable in [callable for callable in localServer.commands if callable[0].lower() == command.lower()]:
                        try:
                            callable[1](self, localServer, recvNoStrip)
                        except Exception as ex:
                            logging.exception(ex)
                            logging.error('Should we disconnect the server because of this issue?')
                    continue

                else:
                    for callable in [callable for callable in localServer.commands if callable[0].lower() == command.lower()]:
                        ### (command, function, params, req_modes, req_flags, req_class, module)
                        ### Do not add a return here, it will stop the recvbuffer read.
                        callable[1](self, localServer, recvNoStrip)

            except Exception as ex:
                logging.exception(ex)
                self.quit(str(ex))

    def chlevel(self, channel):
        return 10000

    def ocheck(self, mode, flag):
        return True

    def __repr__(self):
        return "<Server '{}:{}'>".format('*' if not hasattr(self, 'hostname') else self.hostname, '*' if not hasattr(self, 'sid') else self.sid)

    def quit(self, reason, silent=False, error=False, source=None, squit=True):
        localServer = self.localServer
        logging.info('Server QUIT self: {} :: reason: {}'.format(self, reason))
        if self in localServer.servers:
            logging.info('Removing self {}'.format(self))
            localServer.servers.remove(self)
        self.recvbuffer = ''
        logging.info('Source: {}'.format(source))
        if self.uplink:
            logging.info('Server was uplinked to {}'.format(self.uplink))
        reason = reason[1:] if reason.startswith(':') else reason
        if self in localServer.introducedTo:
            localServer.introducedTo.remove(self)
        try:
            if self.hostname and self.eos:
                logging.info('{}Lost connection to remote server {}: {}{}'.format(R2, self.hostname, reason, W))
                if squit:
                    skip = [self]
                    if self.uplink:
                        skip.append(self.uplink)
                    localServer.new_sync(localServer, skip, ':{} SQUIT {} :{}'.format(localServer.sid, self.hostname, reason))

            if not silent and self.hostname and self.socket:
                if not self.eos and self not in localServer.linkrequester:
                    msg = 'Link denied for server {}: {}'.format(self.hostname, reason)
                else:
                    msg = '{} to server {}: {}'.format('Unable to connect' if not self.eos else 'Lost connection', self.hostname, reason)
                localServer.snotice('s', msg, local=True)
            if self in localServer.linkrequester:
                del localServer.linkrequester[self]
            self.eos = False

            if self.hostname in localServer.linkRequests:
                del localServer.linkRequests[self.hostname]

            if self.hostname in set(localServer.pendingLinks):
                localServer.pendingLinks.remove(self.hostname)

            if self in localServer.sync_queue:
                del localServer.sync_queue[self]

            if self.socket and reason:
                self._send('ERROR :Closing link: [{}] ({})'.format(self.socket.getpeername()[0] if not self.hostname else self.hostname, reason))

            while self.sendbuffer:
                logging.info('Server {} has sendbuffer remaining: {}'.format(self, self.sendbuffer.rstrip()))
                try:
                    sent = self.socket.send(bytes(self.sendbuffer + '\n', 'utf-8'))
                    self.sendbuffer = self.sendbuffer[sent:]
                except:
                    break

            for user in [user for user in localServer.users if not user.server]:
                user.quit('Unknown connection')

            additional_servers = [server for server in localServer.servers if server.introducedBy == self or server.uplink == self]
            if additional_servers:
                logging.info('Also quitting additional servers: {}'.format(additional_servers))
            users = [user for user in localServer.users if user.server and (user.server == self or user.server in additional_servers)]
            for user in users:
                server1 = self.hostname
                server2 = source.hostname if source else localServer.hostname
                user.quit('{} {}'.format(server1, server2))

            for server in additional_servers:
                logging.info('Quitting server {}'.format(server))
                server.quit('{} {}'.format(self.hostname, source.hostname if source else localServer.hostname))

            if self.socket:
                if localServer.use_poll:
                    localServer.pollerObject.unregister(self.socket)
                try:
                    self.socket.shutdown(socket.SHUT_WR)
                except:
                    pass
                self.socket.close()
                del self.socket

            gc.collect()
            del gc.garbage[:]

            if not localServer.forked:
                logging.debug('[SERVER] Growth after self.quit() (if any):')
                objgraph.show_growth(limit=20)

            del self

        except Exception as ex:
            logging.exception(ex)

    def run(self):
        if self.forked:
            pid = os.fork()
            if pid:
                try:
                    with open(pidfile, 'w') as file:
                        file.write(str(pid))
                except Exception as ex:
                    print('Could not write pidfile. Make sure you have write access: {}'.format(ex))
                    sys.exit()
                    return
                print('PID [{}] forked to the background'.format(pid))
                sys.exit()

            atexit.register(exit_handler)

        from handle.handleSockets import data_handler
        self.datahandler = data_handler(self)
        self.datahandler.run()
        return

    def handle(self, cmd, data, params=None):
        p = ' '.join([':'+self.sid, cmd.upper(), data]).split()
        try:
            for callable in [callable for callable in self.localServer.commands if callable[0].lower() == cmd.lower()]:
                if params:
                    callable[1](self, self.localServer, p, **params)
                else:
                    callable[1](self, self.localServer, p)
        except Exception as ex:
            logging.exception(ex)

    def broadcast(self, users, data, source=None):
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
                users = list(filter(lambda u: 'o' in u.modes and 's' in u.modes and sno in u.snomasks, localServer.users))
            for user in users:
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

        except Exception as ex:
            logging.exception(ex)

    def listenToPort(self, port, type):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("", port))
            self.sock.listen(5)
            if is_sslport(self, port) and self.pre_wrap:
                ### SSL port. certfile="ssl/server.crt", keyfile="ssl/server.key", ca_certs="ssl/client.crt"
                self.sock = self.sslctx.wrap_socket(self.sock, server_side=True)
            if self.use_poll: ### Polling does not work.
                self.pollerObject.register(self.sock, select.POLLIN)
                self.fd_to_socket[self.sock.fileno()] = (self.sock, self)
            print('Server listening on port {} :: {} ({})'.format(port, 'SSL' if is_sslport(self, port) else 'insecure', type))
            #print('Sockets{} pre-wrapped. Polling: {}'.format(' not' if not self.pre_wrap else '', 'yes' if self.use_poll else 'no'))
            return self.sock
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R2, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
            print(e)
            print('Another instance running?')
            sys.exit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='IRCd.')
    parser.add_argument('-c', '--conf', help='Conf file.')
    parser.add_argument('--nofork', help='No fork.',action='store_true')
    parser.add_argument('--rehash', help='Rehash current server.',action='store_true')
    try:
        mkp = 1
        import bcrypt
        parser.add_argument('--mkpasswd', help='Generate bcrypt password')
    except ImportError:
        mkp = 0
    args = parser.parse_args()
    if not mkp:
        args.mkpasswd = None
    if args.mkpasswd:
        hashed = bcrypt.hashpw(args.mkpasswd.encode('utf-8'),bcrypt.gensalt(10)).decode('utf-8')
        print('Your salted password: {}'.format(hashed))
        sys.exit()

    if args.rehash:
        if os.path.isfile(pidfile):
            print('Process already running.')
            with open(pidfile) as p:
                pid = p.read()
                print('Pid: {}'.format(pid))

        sys.exit()

    global conffile
    if not args.conf:
        conffile = 'ircd.conf'
    else:
        conffile = args.conf
    fork = not args.nofork
    version = '{}{}'.format(sys.version_info[0], sys.version_info[1])
    if int(version) < 36:
        print('Python version 3.6 or higher is recommended for better performance.')
        time.sleep(3)
    try:
        S = Server(conffile=conffile, forked=fork)
        S.run()
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        print(e)
