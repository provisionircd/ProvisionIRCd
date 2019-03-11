#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    import faulthandler
    faulthandler.enable()
except:
    pass
import gc
gc.enable()

from ircd import Server
### Import classes.
from classes.user import User
#User = user.User
from handle.functions import is_sslport, check_flood, logging
from modules.m_connect import connectTo
import select
import ssl
import random
import threading
import string
import sys
import os
import hashlib
import time
#rom OpenSSL import SSL

server_cert = 'ssl/server.cert.pem'
server_key = 'ssl/server.key.pem'
ca_certs = 'ssl/curl-ca-bundle.crt'
sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
sslctx.load_cert_chain(certfile=server_cert, keyfile=server_key)
sslctx.load_default_certs(purpose=ssl.Purpose.CLIENT_AUTH)
sslctx.load_verify_locations(cafile=ca_certs)
sslctx.verify_mode = ssl.CERT_NONE

if sys.version_info[0] < 3:
    print('Python 2 is not supported.')
    sys.exit()

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
G = '\033[32m' # green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

class data_handler: #(threading.Thread):
    def __init__(self, server):
        #threading.Thread.__init__(self)
        self.server = server
        self.running = True
        self.listen_socks = self.server.listen_socks

    def run(self):
        while 1:
            try:
                localServer = self.server
                read_users = [user for user in list(localServer.users) if user.socket and user.fileno() != -1]
                write_users = [user for user in list(localServer.users) if user.sendbuffer and user.socket and user.fileno() != -1]

                read_servers = [server for server in list(localServer.servers) if server.socket]
                write_servers = [server for server in list(localServer.servers) if server.socket and server.sendbuffer]

                read, write, error = select.select(list(self.listen_socks) + read_users + read_servers, write_users + write_servers, read_users + read_servers + write_users + write_servers + list(self.listen_socks), 1.0)
                for s in error:
                    logging.error('Error occurred in {}'.format(s))
                for s in write:
                    check_flood(localServer, s)
                    if type(s).__name__ == 'User' or type(s).__name__ == 'Server':
                        try:
                            sent = s.socket.send(bytes(s.sendbuffer, 'utf-8'))
                            s.sendbuffer = s.sendbuffer[sent:]
                            if type(s).__name__ == 'User':
                                s.flood_safe = False
                        except Exception as ex:
                            s.quit('Write error: {}'.format(str(ex)))
                            continue

                for s in read:
                    if type(s).__name__ == 'User' or type(s).__name__ == 'Server':
                        read_socket(localServer, s)
                        continue
                    if self.listen_socks[s] == 'clients':
                        try:
                            path = os.path.abspath(__file__)
                            dir_path = os.path.dirname(path)
                            os.chdir(dir_path)
                            conn, addr = s.accept()
                            conn.settimeout(1.5) ### Look into this.
                            conn_backlog = [user for user in localServer.users if user.socket and not user.registered]
                            logging.info('Accepting client on {} -- fd: {}, with IP {}'.format(s, conn.fileno(), addr[0]))
                            if len(conn_backlog) > 10:
                                logging.warning('Current connection backlog is >{}, so not allowing any more connections for now. Bye.'.format(len(conn_backlog)))
                                conn.close()
                                continue
                            port = conn.getsockname()[1]
                            is_ssl = is_sslport(localServer, port)
                            if is_ssl:
                                is_ssl = 0
                                version = '{}{}'.format(sys.version_info[0], sys.version_info[1])
                                if int(version) >= 36:
                                    conn = sslctx.wrap_socket(conn, server_side=True)
                                    is_ssl = 1
                                else:
                                    conn = ssl.wrap_socket(conn,
                                                            server_side=True,
                                                            certfile=server_cert, keyfile=server_key, ca_certs=ca_certs,
                                                            suppress_ragged_eofs=True,
                                                            cert_reqs=ssl.CERT_NONE,
                                                            ciphers='HIGH'
                                                            )
                                    is_ssl = 1
                                try:
                                    fp = conn.getpeercert(True)
                                    if fp:
                                        ssl_fingerprint = hashlib.sha256(repr(fp).encode('utf-8')).hexdigest()
                                        logging.info('Fingerprint: {}'.format(ssl_fingerprint))
                                except Exception as ex:
                                    logging.exception(ex)
                            conn.setblocking(1)
                            u = User(localServer, conn, addr, is_ssl)
                            gc.collect()
                            if u.fileno() == -1:
                                logging.error('{}Invalid fd for {} -- quit() on user{}'.format(R, u, W))
                                u.quit('Invalid fd')
                                continue
                            try:
                                random_ping = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                                localServer.pings[conn] = random_ping
                                u._send('PING :{}'.format(random_ping))

                            except Exception as ex:
                                #localServer.snotice('t', '[{}](1) {}'.format(addr[0], ex))
                                ogging.exception(ex)
                                u.quit(ex)
                                continue

                        except Exception as ex:
                            try:
                                conn.close()
                            except Exception as ex:
                                logging.exception(ex)
                            logging.exception(ex)
                            continue

                    if self.listen_socks[s] == 'servers':
                        try:
                            path = os.path.abspath(__file__)
                            dir_path = os.path.dirname(path)
                            os.chdir(dir_path)
                            conn, addr = s.accept()
                            conn.settimeout(1)
                            port = conn.getsockname()[1]
                            is_ssl = is_sslport(localServer, port)
                            if is_ssl:
                                server_cert = '../ssl/server.cert.pem'
                                server_key = '../ssl/server.key.pem'
                                ca_certs = '../ssl/curl-ca-bundle.crt'
                                conn = ssl.wrap_socket(conn,
                                                        server_side=True,
                                                        certfile=server_cert, keyfile=server_key, ca_certs=ca_certs,
                                                        suppress_ragged_eofs=True,
                                                        do_handshake_on_connect=False,
                                                        #cert_reqs=ssl.CERT_OPTIONAL,
                                                        ciphers='HIGH'
                                                        )

                                conn.do_handshake()
                                logging.info('Wrapped incoming socket {} in SSL'.format(conn))
                                if not conn:
                                    continue
                            Server(origin=localServer, serverLink=True, sock=conn, is_ssl=is_ssl)

                        except ssl.SSLError as ex:
                            localServer.snotice('t', '[{}](3) {}'.format(addr[0], ex))
                            logging.exception(ex)
                            continue
                        except Exception as ex:
                            localServer.snotice('t', '[{}](4) {}'.format(addr[0], ex))
                            logging.exception(ex)
                            continue

                '''
                Checks related to users
                '''
                pingfreq = 120
                users = (user for user in localServer.users if user.socket)
                for user in (user for user in users if time.time() - user.ping > pingfreq and time.time() - user.lastPingSent > pingfreq/2):
                    user.lastPingSent = int(time.time())
                    try:
                        user._send('PING :{}'.format(localServer.hostname))
                    except OSError as ex:
                        user.quit('Write error: {}'.format(str(ex)))

                users = (user for user in localServer.users if user.socket and time.time() - user.ping > 180.0)
                for user in users:
                    user.quit('Ping timeout: {} seconds'.format(int(time.time() - user.ping)))
                    ### Expire all invites after 6 hours.
                    channels = (channel for channel in localServer.channels if len(channel.invites) > 0)
                    for chan in channels:
                        for invite in (chan.invites):
                            if time.time() - chan.invites[invite]['ctime'] > 3600.0*6:
                                del chan.invites[invite]

                for t in (localServer.tkl):
                    for mask in dict(localServer.tkl[t]):
                        expire = localServer.tkl[t][mask]['expire']
                        if expire == '0':
                            continue
                        if int(time.time()) > expire:
                            mask = '{} {}'.format(mask.split('@')[0], mask.split('@')[1])
                            data = '- {} {}'.format(t, mask)
                            p = {'expire': True}
                            localServer.handle('tkl', data, params=p)

                ### Request links
                if localServer.users:
                    linkServers = [link for link in localServer.conf['link'] if link.lower() != localServer.hostname.lower() and 'outgoing' in localServer.conf['link'][link] and 'options' in localServer.conf['link'][link] and not list(filter(lambda s: s.hostname == link, localServer.servers))]
                    servers = (link for link in linkServers if link not in localServer.linkRequests)
                    for link in servers:
                        localServer.linkRequests[link] = {}
                        localServer.linkRequests[link]['ctime'] = int(time.time())

                    servers = (link for link in linkServers if 'autoconnect' in localServer.conf['link'][link]['options'])
                    for link in (link for link in servers if time.time() - localServer.linkRequests[link]['ctime'] > 900.0):
                        localServer.linkRequests[link] = {}
                        localServer.linkRequests[link]['ctime'] = int(time.time())
                        logging.info('Connecting to {}'.format(link))
                        connectTo(None, localServer, link, autoLink=True)

                if len(localServer.dnsblCache) >= 1024:
                    del localServer.dnsblCache[localServer.dnsblCache[0]]

                if len(localServer.hostcache) >= 1024:
                    del localServer.hostcache[localServer.hostcache[0]]

                ### Remove cached host look-ups after 6 hours.
                for host in (host for host in dict(localServer.hostcache) if int(time.time()) - localServer.hostcache[host]['ctime'] > 3600.0*6):
                    del localServer.hostcache[host]

                ### Remove cached DNSBL after 1 day.
                for host in (host for host in dict(localServer.dnsblCache) if int(time.time()) - localServer.dnsblCache[host]['ctime'] > 3600.0*24):
                    del localServer.dnsblCache[host]

                ### Check for unregistered connections.
                for user in (user for user in list(localServer.users) if user.socket and not user.registered):
                    if time.time() - user.signon >= int(localServer.conf['settings']['regtimeout']):
                        user.quit('Registration timed out')
                        continue

                conn_backlog = [user for user in localServer.users if user.socket and not user.registered]
                for user in conn_backlog:
                    totalIP = list(filter(lambda s: s.ip == user.ip, conn_backlog))
                    if len(totalIP) > 2:
                        user.quit('Too many unknown connections from your IP')
                        continue

                for throttle in (throttle for throttle in dict(localServer.throttle) if int(time.time()) - localServer.throttle[throttle]['ctime'] > int(localServer.conf['settings']['throttle'].split(':')[1])):
                    del localServer.throttle[throttle]
                    continue

                for user in (user for user in localServer.users if user in localServer.nickflood):
                    for nickchg in (nickchg for nickchg in dict(localServer.nickflood[user]) if int(time.time()) - int(nickchg) > int(localServer.conf['settings']['nickflood'].split(':')[1])):
                        del localServer.nickflood[user][nickchg]
                        continue

                ### Check for timed channels status.
                modify_status = {}
                for chan in localServer.channels:
                    try:
                        for user in dict(chan.temp_status):
                            for mode in chan.temp_status[user]:
                                exp = chan.temp_status[user][mode]['ctime']
                                if int(time.time()) >= exp:
                                    param = '{}{} {}'.format(chan.temp_status[user][mode]['action'], mode, user.nickname)
                                    if chan not in modify_status:
                                        modify_status[chan] = []
                                    modify_status[chan].append(param)
                                    del chan.temp_status[user]
                    except:
                        pass
                    if chan in modify_status:
                        modes = []
                        for mode in modify_status[chan]:
                            modes.append(mode)
                        localServer.handle('MODE', '{} {} 0'.format(chan.name, ' '.join(modes)))

                '''
                Checks related to servers
                '''
                # Send out pings
                pingfreq = 60
                servers = (server for server in localServer.servers if server.socket and server.hostname)
                for server in (server for server in servers if time.time() - server.ping > pingfreq and time.time() - server.lastPingSent > pingfreq/2):
                    server.lastPingSent = int(time.time())
                    try:
                        server._send(':{} PING {} {}'.format(localServer.sid, localServer.hostname, server.hostname))
                    except OSError as ex:
                        server.quit('Write error: {}'.format(str(ex)))

                # Ping timeouts (only for direct links)
                for server in (server for server in localServer.servers if server.hostname and server.socket and time.time() - server.ping >= 120.0):
                    server.quit('Ping timeout: {} seconds'.format(int(time.time() - server.ping)))

                # Registration timeouts
                for server in [server for server in localServer.servers if (not server.eos and (server.introducedBy and not server.introducedBy.eos)) and time.time() - server.ping >= 10.0]:
                    is_silent = False if server.socket else True
                    server.quit('Server registration timed out', silent=is_silent)

                # Check for unknown or timed out servers (non-sockets)
                for server in [server for server in localServer.servers if not server.socket and server.uplink and server.uplink.socket and time.time() - server.uplink.ping >= 120.0]:
                    is_silent = False if server.socket else True
                    server.quit('Server uplink ping timed out: {} seconds'.format(int(time.time() - server.uplink.ping)))

                for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'loop']:
                    try:
                        callable[2](localServer)
                    except Exception as ex:
                        logging.exception(ex)

            except Exception as ex:
                logging.exception(ex)

        logging.warning('data_handler loop broke! This should only happen if you reload the core, or after /restart.')

def read_socket(localServer, sock):
    try:
        if sock.cls:
            buffer_len = int(localServer.conf['class'][sock.cls]['sendq']) * 2
        else:
            buffer_len = 4096 if type(sock).__name__ == 'User' else 16384
        try:
            recv = sock.socket.recv(buffer_len).decode('utf-8')
        except Exception as ex:
            logging.exception(ex)
            sock.quit('Read error: {}'.format(ex))
            return

        if not recv:
            sock.quit('Read error')
            return

        sock.recvbuffer += recv
        check_flood(localServer, sock)
        sock.handle_recv()
    except Exception as ex:
        logging.exception(ex)
