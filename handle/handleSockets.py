#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gc
gc.enable()

from ircd import Server
### Import classes.
from classes.user import User
#User = user.User
from handle.functions import _print, is_sslport, check_flood
import select
import ssl
import random
import threading
import string
import sys
import os
import hashlib
import time
#from OpenSSL import SSL

if sys.version_info[0] < 3:
    print('Python 2 is not supported.')
    sys.exit()

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
G = '\033[32m' # green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

class data_handler(threading.Thread):
    def __init__(self, server):
        threading.Thread.__init__(self)
        self.server = server
        self.running = True
        self.listen_socks = self.server.listen_socks

    def run(self):
        while self.server.running and self.running:
            localServer = self.server
            read_users = [user for user in localServer.users if user.socket and user.fileno() != -1]
            write_users = [user for user in localServer.users if user.sendbuffer and user.socket and user.fileno() != -1]

            read_servers = [server for server in localServer.servers if server.socket]
            write_servers = [server for server in localServer.servers if server.socket and server.sendbuffer]

            read, write, error = select.select(list(self.listen_socks) + read_users + read_servers, write_users + write_servers, read_users, 1.0)
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
                        conn_backlog = [user for user in localServer.users if user.socket and not user.registered]
                        _print('Accepting client on {} -- fd: {}, with IP {}'.format(s, conn.fileno(), addr[0]), server=localServer)
                        if len(conn_backlog) > 100:
                            _print('Current connection backlog is >{}, so not allowing any more connections for now. Bye.'.format(len(conn_backlog)), server=localServer)
                            conn.close()
                            continue
                        conn_backlog = []
                        ban = False

                        for entry in [entry for entry in localServer.bannedList if len(entry) > 5 and '.' in entry]:
                            if match(entry, addr[0]) or entry == addr[0]:
                                ban = True
                                break
                        if addr[0] in localServer.dnsblCache or ban:
                            _print('User banned?', server=localServer)
                            conn.close()
                            continue
                        port = conn.getsockname()[1]
                        is_ssl = is_sslport(localServer, port)
                        if is_ssl:
                            server_cert = '../ssl/server.cert.pem'
                            server_key = '../ssl/server.key.pem'
                            ca_certs = '../ssl/curl-ca-bundle.crt'
                            '''
                            conn = ssl.wrap_socket(conn,
                                                    server_side=True,
                                                    certfile=server_cert, keyfile=server_key, ca_certs=ca_certs,
                                                    suppress_ragged_eofs=True,
                                                    #cert_reqs=ssl.CERT_OPTIONAL,
                                                    ciphers='HIGH'
                                                    )
                            '''
                            sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
                            sslctx.load_cert_chain(certfile=server_cert, keyfile=server_key)
                            sslctx.load_default_certs(purpose=ssl.Purpose.CLIENT_AUTH)
                            sslctx.load_verify_locations(cafile=ca_certs)
                            sslctx.verify_mode = ssl.CERT_NONE
                            conn = sslctx.wrap_socket(conn, server_side=True)

                            try:
                                fp = conn.getpeercert(True)
                                if fp:
                                    ssl_fingerprint = hashlib.sha256(repr(conn.getpeercert()).encode('utf-8')).hexdigest()
                                    _print('Fingerprint: {}'.format(ssl_fingerprint), server=localServer)
                            except Exception as ex:
                                _print(ex, server=localServer)

                        u = User(localServer, conn, addr, is_ssl)
                        gc.collect()
                        if u.fileno() == -1:
                            _print('{}Invalid fd for {} -- quit() on user{}'.format(R, u, W), server=localServer)
                            u.quit('Invalid fd')
                            continue
                        try:
                            random_ping = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                            localServer.pings[conn] = random_ping
                            conn.send(bytes('PING :{}\r\n'.format(random_ping), 'utf-8'))

                        except Exception as ex:
                            #localServer.snotice('t', '[{}](1) {}'.format(addr[0], ex))
                            #exc_type, exc_obj, exc_tb = sys.exc_info()
                            #fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            #e = '{}EXCEPTION after accept: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
                            #_print(e, server=localServer)
                            u.quit(ex)
                            continue

                    except Exception as ex:
                        localServer.snotice('t', '[{}](2) {}'.format(addr[0],ex))
                        conn.close()
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        e = '{}EXCEPTION after conn.close: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
                        _print(e, server=localServer)
                        continue

                if self.listen_socks[s] == 'servers':
                    try:
                        path = os.path.abspath(__file__)
                        dir_path = os.path.dirname(path)
                        os.chdir(dir_path)
                        conn, addr = s.accept()
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
                            while True:
                                try:
                                    conn.do_handshake()
                                    break
                                except ssl.SSLError as ex:
                                    pass

                            _print('Wrapped incoming socket {} in SSL'.format(conn), server=localServer)
                            if not conn:
                                continue
                        Server(origin=localServer, serverLink=True, sock=conn, is_ssl=is_ssl)

                    except ssl.SSLError as ex:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        localServer.snotice('t', '[{}]3 {}'.format(addr[0], ex))
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                        _print(e, server=localServer)
                        continue
                    except OSError as ex:
                        localServer.snotice('t', '[{}]4 {}'.format(addr[0], ex))
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                        _print(e, server=localServer)
                        continue

            '''
            Checks related to users
            '''
            # Send out pings
            pingfreq = 120
            users = (user for user in localServer.users if user.socket)
            for user in (user for user in users if time.time() - user.ping > pingfreq and time.time() - user.lastPingSent > pingfreq/2):
                user.lastPingSent = int(time.time())
                try:
                    user.socket.send(bytes('PING :{}\r\n'.format(localServer.hostname), 'utf-8'))
                except OSError as ex:
                    user.quit('Write error: {}'.format(str(ex)))
            # Ping timeouts
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
                    _print('Connecting to {}'.format(link), server=localServer)
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
                    server.socket.send(bytes(':{} PING {} {}\r\n'.format(localServer.sid, localServer.hostname, server.hostname), 'utf-8'))
                except OSError as ex:
                    server.quit('Write error: {}'.format(str(ex)))

            # Ping timeouts
            for server in (server for server in localServer.servers if server.hostname and server.socket and time.time() - server.ping >= 120.0):
                server.quit('Ping timeout: {} seconds'.format(int(time.time() - server.ping)))

            # Ping timeouts
            for server in [server for server in localServer.servers if (not server.eos and (server.introducedBy and not server.introducedBy.eos)) and time.time() - server.ping >= 10.0]:
                is_silent = False if server.socket else True
                server.quit('Server registration timed out', silent=is_silent)

        _print('data_handler loop broke! This should only happen if you reload the core, or after /restart.', server=localServer)

def read_socket(localServer, sock):
    if sock.cls:
        buffer_len = int(localServer.conf['class'][sock.cls]['sendq']) * 2
    else:
        buffer_len = 4096 if type(sock).__name__ == 'User' else 16384
    try:
        recv = sock.socket.recv(buffer_len).decode('utf-8')
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} on line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
        sock.quit('Read error: {}'.format(ex))
        return

    if not recv:
        sock.quit('Read error')
        return

    sock.recvbuffer += recv
    check_flood(localServer, sock)
    sock.handle_recv()
