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
from handle.functions import is_sslport, check_flood, logging, save_db
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

if sys.version_info[0] < 3:
    print('Python 2 is not supported.')
    sys.exit()

W = '\033[0m'  # white (normal)
R = '\033[31m' # red

READ_ONLY = (
    select.POLLIN |
    select.POLLPRI |
    select.POLLHUP |
    select.POLLERR
)
READ_WRITE = READ_ONLY | select.POLLOUT

def sock_accept(localServer, s):
    if localServer.listen_socks[s] == 'clients':
        try:
            conn, addr = s.accept()
            if localServer.use_poll:
                localServer.pollerObject.register(conn, READ_ONLY)
            port = conn.getsockname()[1]
            is_ssl = is_sslport(localServer, port)
            conn_backlog = [user for user in localServer.users if user.socket and not user.registered]
            logging.info('Accepting client on {} -- fd: {}, with IP {}'.format(s, conn.fileno(), addr[0]))
            if len(conn_backlog) > 500:
                logging.warning('Current connection backlog is >{}, so not allowing any more connections for now. Bye.'.format(len(conn_backlog)))
                conn.close()
                return
            conn.settimeout(10)
            if is_ssl and not localServer.pre_wrap:
                is_ssl = 0
                version = '{}{}'.format(sys.version_info[0], sys.version_info[1])
                if int(version) >= 36:
                    conn = localServer.sslctx.wrap_socket(conn, server_side=True)
                    is_ssl = 1
                else:
                    conn = ssl.wrap_socket(conn,
                                            #server_side=True,
                                            certfile=localServer.server_cert, keyfile=localServer.server_key, ca_certs=localServer.ca_certs,
                                            suppress_ragged_eofs=True,
                                            cert_reqs=ssl.CERT_NONE,
                                            ciphers='HIGH'
                                            )
                    is_ssl = 1
                logging.info('Wrapped incoming user socket {} in SSL'.format(conn))
                try:
                    fp = conn.getpeercert(True)
                    if fp:
                        ssl_fingerprint = hashlib.sha256(repr(fp).encode('utf-8')).hexdigest()
                        logging.info('Fingerprint: {}'.format(ssl_fingerprint))
                except Exception as ex:
                    logging.exception(ex)
            u = User(localServer, conn, addr, is_ssl)
            if localServer.use_poll:
                localServer.fd_to_socket[u.fileno()] = (u.socket, u)

            try:
                u.socket.setblocking(1) ### Uncomment this. Why? I don't remember.
            except OSError as ex:
                logging.debug(R+'Client {} probably refused the connection due to self-signed cert (ZNC?). This can cause memory leaks.'.format(u)+W)
                logging.debug(R+'Gently disconnecting user. IP: {}'.format(u.ip)+W)
                #logging.exception(ex)
                u.quit(ex)
                return
            gc.collect()
            if u.fileno() == -1:
                logging.error('{}Invalid fd for {} -- quit() on user{}'.format(R, u, W))
                u.quit('Invalid fd')
                return
            try:
                random_ping = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                localServer.pings[u] = random_ping
                u._send('PING :{}'.format(random_ping))

            except Exception as ex:
                #localServer.snotice('t', '[{}](1) {}'.format(addr[0], ex))
                logging.exception(ex)
                u.quit(ex)
                return

        except Exception as ex:
            logging.exception(ex)
            conn.close()
            return

    elif localServer.listen_socks[s] == 'servers':
        try:
            conn, addr = s.accept()
            if localServer.use_poll:
                localServer.pollerObject.register(conn, READ_ONLY)
            port = conn.getsockname()[1]
            is_ssl = is_sslport(localServer, port)

            if is_ssl and not localServer.pre_wrap:
                version = '{}{}'.format(sys.version_info[0], sys.version_info[1])
                if int(version) >= 36:
                    conn = localServer.sslctx.wrap_socket(conn, server_side=True)
                else:
                    conn = ssl.wrap_socket(conn,
                                            server_side=True,
                                            certfile=localServer.server_cert, keyfile=localServer.server_key, ca_certs=localServer.ca_certs,
                                            suppress_ragged_eofs=True,
                                            do_handshake_on_connect=False,
                                            #cert_reqs=ssl.CERT_OPTIONAL,
                                            ciphers='HIGH'
                                            )
                    conn.do_handshake()
                logging.info('Wrapped incoming server socket {} in SSL'.format(conn))

            s = Server(origin=localServer, serverLink=True, sock=conn, is_ssl=is_ssl)

        except ssl.SSLError as ex:
            logging.exception(ex)
            return
        except Exception as ex:
            logging.exception(ex)
            return

class data_handler: #(threading.Thread):
    def __init__(self, server):
        #threading.Thread.__init__(self)
        self.server = server
        self.running = True
        self.listen_socks = self.server.listen_socks

    def run(self):
        localServer = self.server
        while 1:
            try:
                if localServer.use_poll:
                    fdVsEvent = localServer.pollerObject.poll(1000)
                    #print('y u no read? {}'.format(fdVsEvent))
                    for fd, Event in fdVsEvent:
                        try:
                            s = localServer.fd_to_socket[fd][0]
                            c = localServer.fd_to_socket[fd][1]
                            t = type(c).__name__

                            if Event & (select.POLLIN | select.POLLPRI):
                                logging.debug('POLLIN for {}'.format(c))
                                if s in self.listen_socks:
                                    logging.debug('Incoming connection on {}'.format(s))
                                    threading.Thread(target=sock_accept, args=([localServer, s])).start()

                                elif t in ['User', 'Server']:
                                    logging.debug('Reading data from {}'.format(c))
                                    read_socket(localServer, c)
                                try:
                                    localServer.pollerObject.modify(s, READ_WRITE)
                                    logging.debug('Flag for {} set to READ_WRITE'.format(c))
                                except FileNotFoundError: ### Already closed.
                                    pass
                                continue
                            elif Event & select.POLLOUT:
                                logging.debug('POLLOUT for {} ({})'.format(s, c))
                                if c.sendbuffer:
                                    logging.debug('Sending data to {}'.format(c))
                                    check_flood(localServer, c)
                                    try:
                                        sent = s.send(bytes(c.sendbuffer, 'utf-8'))
                                        c.sendbuffer = c.sendbuffer[sent:]
                                    except Exception as ex:
                                        logging.exception(ex)
                                        c.quit('Write error')
                                        time.sleep(1000)
                                logging.debug('Flag for {} set to READ_ONLY'.format(c))
                                localServer.pollerObject.modify(s, READ_ONLY)
                                continue
                            elif Event & select.POLLHUP:
                                #localServer.pollerObject.unregister(s)
                                c.quit('Hung up poll')

                            elif Event & select.POLLERR:
                                #localServer.pollerObject.unregister(s)
                                c.quit('Polling error')
                        except Exception as ex:
                            logging.exception(ex)
                            time.sleep(1000)

                        check_loops(localServer)
                        continue
                else:
                    #localServer = self.server
                    read_users = [user for user in list(localServer.users) if user.socket and user.fileno() != -1]
                    write_users = [user for user in list(localServer.users) if user.sendbuffer and user.socket and user.fileno() != -1]

                    read_servers = [server for server in list(localServer.servers) if server.socket and server.fileno() != -1]
                    write_servers = [server for server in list(localServer.servers) if server.socket and server.sendbuffer and server.fileno() != -1]

                    try:
                        read, write, error = select.select(list(self.listen_socks) + read_users + read_servers, write_users + write_servers, read_users + read_servers + write_users + write_servers + list(self.listen_socks), 1.0)
                    except ValueError as ex:
                        for fd in [fd for fd in list(localServer.users) if fd.socket and not fd.registered]:
                            fd.quit('Limit reached')
                        logging.info('Cleanup done')
                        logging.exception(ex)
                        continue

                    for s in error:
                        logging.error('Error occurred in {}'.format(s))
                    for s in write:
                        check_flood(localServer, s)
                        if type(s).__name__ == 'User' or type(s).__name__ == 'Server':
                            try:
                                sent = s.socket.send(bytes(s.sendbuffer, 'utf-8'))
                                s.sendbuffer = s.sendbuffer[sent:]
                                if type(s).__name__ == 'User' and (hasattr(s, 'flood_safe') and s.flood_safe):
                                    s.flood_safe = False
                                    logging.debug('Flood_safe for {} unset.'.format(s))
                            except Exception as ex:
                                s.quit('Write error: {}'.format(str(ex)))
                                continue

                    for s in read:
                        if type(s).__name__ in ['User', 'Server']:
                            read_socket(localServer, s)
                            continue
                        if self.listen_socks[s] in ['clients', 'servers']:
                            threading.Thread(target=sock_accept, args=([localServer, s])).start()
                            continue
                    check_loops(localServer)
            except Exception as ex:
                logging.exception(ex)
        logging.warning('data_handler loop broke! This should only happen after /restart.')

def check_loops(localServer):
    '''
    Checks related to users
    '''
    pingfreq = 120
    users = (user for user in localServer.users if user.socket)
    for user in (user for user in users if time.time() - user.ping > pingfreq and time.time()*1000 - user.lastPingSent > pingfreq/2):
        user.lastPingSent = time.time() * 1000
        user.lag_measure = user.lastPingSent
        user._send('PING :{}'.format(localServer.hostname))

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
            logging.info('Auto connecting to {}'.format(link))
            connectTo(None, localServer, link, autoLink=True)

    if len(localServer.dnsblCache) >= 1024:
        del localServer.dnsblCache[localServer.dnsblCache[0]]

    if len(localServer.hostcache) >= 1024:
        del localServer.hostcache[localServer.hostcache[0]]

    if len(localServer.deny_cache) >= 1024:
        del localServer.deny_cache[localServer.deny_cache[0]]

    ### Remove cached host look-ups after 6 hours.
    for host in (host for host in dict(localServer.hostcache) if int(time.time()) - localServer.hostcache[host]['ctime'] > 3600.0*6):
        del localServer.hostcache[host]

    ### Remove cached DNSBL after 1 day.
    for host in (host for host in dict(localServer.dnsblCache) if int(time.time()) - localServer.dnsblCache[host]['ctime'] > 3600.0*24):
        del localServer.dnsblCache[host]

    ### Remove cached Deny entries after 1 day.
    for host in (host for host in dict(localServer.deny_cache) if int(time.time()) - localServer.deny_cache[host]['ctime'] > 3600.0*24):
        del localServer.deny_cache[host]

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
    for server in (server for server in servers if time.time() - server.ping > pingfreq and time.time() * 1000 - server.lastPingSent > pingfreq/2):
        server.lastPingSent = time.time() * 1000
        #server.lag_measure = server.lastPingSent
        try:
            server._send(':{} PING {} {}'.format(localServer.sid, localServer.hostname, server.hostname))
        except OSError as ex:
            server.quit('Write error: {}'.format(str(ex)))

    # Ping timeouts (only for direct links)
    for server in (server for server in localServer.servers if server.hostname and server.socket and time.time() - server.ping >= 120.0):
        server.quit('Ping timeout: {} seconds'.format(int(time.time() - server.ping)))

    # Registration timeouts
    for server in [server for server in localServer.servers if not server.eos and ((server.introducedBy and not server.introducedBy.eos) or server.socket) and time.time() - server.ping >= 10.0]:
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

    if not os.path.exists('logs'):
        os.mkdir('logs')

    if not os.path.exists('db'):
        os.mkdir('db')

def read_socket(localServer, sock):
    if not hasattr(sock, 'socket'):
        # Client probably repidly disconnected. Possible causes can be ZNC that have not yet accepted new cert.
        #sock.quit('No socket')
        return

    try:
        if sock.cls:
            buffer_len = int(localServer.conf['class'][sock.cls]['sendq']) * 2
        else:
            buffer_len = 8192 if type(sock).__name__ == 'User' else 65536
        try:
            recv = sock.socket.recv(buffer_len).decode('utf-8')
        except Exception as ex:
            logging.exception(ex)
            sock.quit('Read error: {}'.format(ex))
            return

        if not recv:
            #logging.error('No data received from {}'.format(sock))
            sock.quit('Read error')
            return

        sock.recvbuffer += recv
        check_flood(localServer, sock)
        sock.handle_recv()
        return recv
    except Exception as ex:
        logging.exception(ex)
