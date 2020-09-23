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
import itertools


W = '\033[0m'  # white (normal)
R = '\033[31m' # red

READ_ONLY = (
    select.POLLIN |
    select.POLLPRI |
    select.POLLHUP |
    select.POLLERR
)
READ_WRITE = READ_ONLY | select.POLLOUT




def listen_socks(ircd):
    for i in range(len(ircd.listen_socks)):
        yield list(ircd.listen_socks)[i]


def users(ircd, mode='r'):
    # Defaults to read mode. Returns all users for reading.
    for i in range(len(ircd.users)):
        u = ircd.users[i]
        if mode == 'r':
            if u.socket and u.socket.fileno() != -1:
                yield u
        elif mode == 'w':
            if u.socket and u.sendbuffer and u.socket.fileno() != -1:
                yield u
        elif mode == 'a': # All
            yield u


def servers(ircd, mode='r'):
    # Defaults to read mode. Returns all servers for reading.
    for i in range(len(ircd.servers)):
        s = ircd.servers[i]
        if mode == 'r':
            if s.socket and s.socket.fileno() != -1:
                yield s
        elif mode == 'w':
            if s.socket and s.sendbuffer and s.socket.fileno() != -1:
                yield s


def channels(ircd):
    for i in range(len(ircd.channels)):
        yield ircd.channels[i]


def read_recv(recv):
    idx = 0
    for count,line in enumerate(recv.split('\n')):
        idx += 1
        line = line.strip()
        if not line:
            continue
        #print(f"+++ inside read_recv(): {recv.split('\n')[count]}")
        #print(line)
        #print(line)
        yield line


def sock_accept(ircd, s):
    if ircd.listen_socks[s] == 'clients':
        try:
            conn, addr = s.accept()
            if ircd.use_poll:
                ircd.pollerObject.register(conn, READ_ONLY)
            port = conn.getsockname()[1]
            tls = is_sslport(ircd, port)
            conn_backlog = [user for user in ircd.users if user.socket and not user.registered]
            logging.info('Accepting client on {} -- fd: {}, with IP {}'.format(s, conn.fileno(), addr[0]))
            if len(conn_backlog) > 100:
                logging.warning('Current connection backlog is >{}, so not allowing any more connections for now. Bye.'.format(len(conn_backlog)))
                conn.close()
                return
            conn.settimeout(15)
            if tls and not ircd.pre_wrap:
                tls = 0
                version = '{}{}'.format(sys.version_info[0], sys.version_info[1])
                conn = ircd.sslctx[str(port)].wrap_socket(conn, server_side=True)
                tls = 1
                logging.info('Wrapped incoming user socket {} in TLS'.format(conn))
                try:
                    fp = conn.getpeercert(True)
                    if fp:
                        tls_fingerprint = hashlib.sha256(repr(fp).encode('utf-8')).hexdigest()
                        logging.info('Fingerprint: {}'.format(tls_fingerprint))
                except Exception as ex:
                    logging.exception(ex)
            u = User(ircd, conn, addr, tls)
            if ircd.use_poll:
                ircd.fd_to_socket[u.fileno()] = (u.socket, u)

            '''
            try:
                u.socket.setblocking(1) ### Uncomment this. Why? I don't remember.
            except OSError as ex:
                logging.debug(R+'Client {} probably refused the connection due to self-signed cert (ZNC?). This can cause memory leaks.'.format(u)+W)
                logging.debug(R+'Gently disconnecting user. IP: {}'.format(u.ip)+W)
                #logging.exception(ex)
                u.quit(ex)
                return
            '''

            gc.collect()
            if u.fileno() == -1:
                logging.error('{}Invalid fd for {} -- quit() on user{}'.format(R, u, W))
                u.quit('Invalid fd')
                return
            try:
                random_ping = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                ircd.pings[u] = random_ping
                u._send('PING :{}'.format(random_ping))

            except Exception as ex:
                #ircd.snotice('t', '[{}](1) {}'.format(addr[0], ex))
                logging.exception(ex)
                u.quit(ex)
                return

        except Exception as ex:
            logging.exception(ex)
            conn.close()
            return

    elif ircd.listen_socks[s] == 'servers':
        try:
            conn, addr = s.accept()
            if ircd.use_poll:
                ircd.pollerObject.register(conn, READ_ONLY)
            port = conn.getsockname()[1]
            tls = is_sslport(ircd, port)
            conn.settimeout(15)
            if tls and not ircd.pre_wrap:
                tls = 0
                version = '{}{}'.format(sys.version_info[0], sys.version_info[1])
                conn = ircd.sslctx[str(port)].wrap_socket(conn, server_side=True)
                tls = 1
                logging.info('Wrapped incoming server socket {} in TLS'.format(conn))

            s = Server(origin=ircd, serverLink=True, sock=conn, is_ssl=tls)

        except ssl.SSLError as ex:
            logging.exception(ex)
            return
        except Exception as ex:
            logging.exception(ex)
            return


class data_handler: #(threading.Thread):
    def __init__(self, ircd):
        #threading.Thread.__init__(self)
        self.ircd = ircd
        self.listen_socks = self.ircd.listen_socks

    def run(self):
        ircd = self.ircd
        while ircd.running:
            try:

                if ircd.use_poll:
                    fdVsEvent = ircd.pollerObject.poll(1000)
                    for fd, Event in fdVsEvent:
                        try:
                            s = ircd.fd_to_socket[fd][0]
                            c = ircd.fd_to_socket[fd][1]
                            t = type(c).__name__

                            if Event & (select.POLLIN | select.POLLPRI):
                                logging.debug('POLLIN for {}'.format(c))
                                if s in self.listen_socks:
                                    logging.debug('Incoming connection on {}'.format(s))
                                    threading.Thread(target=sock_accept, args=([ircd, s])).start()

                                elif t in ['User', 'Server']:
                                    logging.debug('Reading data from {}'.format(c))
                                    read_socket(ircd, c)
                                try:
                                    ircd.pollerObject.modify(s, READ_WRITE)
                                    logging.debug('Flag for {} set to READ_WRITE'.format(c))
                                except FileNotFoundError: ### Already closed.
                                    pass
                                continue
                            elif Event & select.POLLOUT:
                                logging.debug('POLLOUT for {} ({})'.format(s, c))
                                if c.sendbuffer:
                                    logging.debug('Sending data to {}'.format(c))
                                    check_flood(ircd, c)
                                    try:
                                        sent = s.send(bytes(c.sendbuffer, 'utf-8'))
                                        c.sendbuffer = c.sendbuffer[sent:]
                                    except Exception as ex:
                                        logging.exception(ex)
                                        c.quit('Write error')
                                        time.sleep(1000)
                                logging.debug('Flag for {} set to READ_ONLY'.format(c))
                                ircd.pollerObject.modify(s, READ_ONLY)
                                continue
                            elif Event & select.POLLHUP:
                                #ircd.pollerObject.unregister(s)
                                c.quit('Hung up poll')

                            elif Event & select.POLLERR:
                                #ircd.pollerObject.unregister(s)
                                c.quit('Polling error')
                        except Exception as ex:
                            logging.exception(ex)
                            time.sleep(1000)

                        check_loops(ircd)
                        continue

                else:
                    read_clients = itertools.chain(listen_socks(ircd), users(ircd), servers(ircd))
                    write_clients = itertools.chain(users(ircd, 'w'), servers(ircd, 'w'))

                    #print(f"Size of read_clients: {sys.getsizeof(read_clients)}")
                    try:
                        read, write, error = select.select(read_clients, write_clients, read_clients, 1.0)
                                                # read and error need the same iteratable.

                        #read, write, error = select.select(list(self.listen_socks) + read_users + read_servers, write_users + write_servers, read_users + #read_servers + write_users + write_servers + list(self.listen_socks), 1.0)
                    except ValueError as ex:
                        for fd in iter([fd for fd in iter(ircd.users) if fd.socket and not fd.registered]):
                            fd.quit('Limit reached')
                        logging.info('Cleanup done')
                        logging.exception(ex)
                        continue


                    for s in error:
                        logging.error('Error occurred in {}'.format(s))

                    for s in read:
                        if s in write: # Write first.
                            continue
                        if type(s).__name__ in ['User', 'Server']:
                            read_socket(ircd, s)
                            continue
                        if self.listen_socks[s] in ['clients', 'servers']:
                            threading.Thread(target=sock_accept, args=([ircd, s])).start()
                            continue

                    for s in write:

                        check_flood(ircd, s)
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

                    check_loops(ircd)
            except KeyboardInterrupt as ex:
                #cleanup(ircd)
                os._exit(0)
                return

            except Exception as ex:
                logging.exception(ex)
                break
        os._exit(0)
        logging.warning('data_handler loop broke! This should only happen after /restart.')


def check_loops(ircd):
    '''
    Checks related to users
    '''
    pingfreq = 120
    users = iter([user for user in iter(ircd.users) if user.socket])

    for user in iter([user for user in users if time.time() - user.ping > pingfreq and time.time()*1000 - user.lastPingSent > pingfreq/2]):
        user.lastPingSent = time.time() * 1000
        user.lag_measure = user.lastPingSent
        user._send('PING :{}'.format(ircd.hostname))

    ping_users = [user for user in users if time.time() - user.ping >= 180.0]

    for user in list(ping_users):
        user.quit('Ping timeout: {} seconds'.format(int(time.time() - user.ping)))

    for t in iter(ircd.tkl):
        for mask in dict(ircd.tkl[t]):
            expire = ircd.tkl[t][mask]['expire']
            if expire == '0':
                continue
            if int(time.time()) > expire:
                mask = '{} {}'.format(mask.split('@')[0], mask.split('@')[1])
                data = '- {} {}'.format(t, mask)
                p = {'expire': True}
                ircd.handle('tkl', data, params=p)

    ### Request links
    if ircd.users:
        linkServers = iter([link for link in ircd.conf['link'] if link.lower() != ircd.hostname.lower() and 'outgoing' in ircd.conf['link'][link] and 'options' in ircd.conf['link'][link] and not list(filter(lambda s: s.hostname == link, ircd.servers))])
        servers = iter([link for link in linkServers if link not in ircd.linkRequests])
        for link in servers:
            ircd.linkRequests[link] = {}
            ircd.linkRequests[link]['ctime'] = int(time.time())

        servers = iter([link for link in linkServers if 'autoconnect' in ircd.conf['link'][link]['options']])
        for link in iter([link for link in servers if time.time() - ircd.linkRequests[link]['ctime'] > 900.0]):
            ircd.linkRequests[link] = {}
            ircd.linkRequests[link]['ctime'] = int(time.time())
            logging.info('Auto connecting to {}'.format(link))
            connectTo(None, ircd, link, autoLink=True)

    if len(ircd.dnsblCache) >= 1024:
        del ircd.dnsblCache[ircd.dnsblCache[0]]

    if len(ircd.hostcache) >= 1024:
        del ircd.hostcache[ircd.hostcache[0]]

    if len(ircd.deny_cache) >= 1024:
        del ircd.deny_cache[ircd.deny_cache[0]]

    ### Remove cached host look-ups after 6 hours.
    for host in iter([host for host in dict(ircd.hostcache) if int(time.time()) - ircd.hostcache[host]['ctime'] > 3600.0*6]):
        del ircd.hostcache[host]

    ### Remove cached DNSBL after 1 day.
    for host in iter([host for host in dict(ircd.dnsblCache) if int(time.time()) - ircd.dnsblCache[host]['ctime'] > 3600.0*24]):
        del ircd.dnsblCache[host]

    ### Remove cached Deny entries after 1 day.
    for host in iter([host for host in dict(ircd.deny_cache) if int(time.time()) - ircd.deny_cache[host]['ctime'] > 3600.0*24]):
        del ircd.deny_cache[host]

    ### Check for unregistered connections.
    for user in iter([user for user in list(ircd.users) if user.socket and not user.registered]):
        if time.time() - user.signon >= int(ircd.conf['settings']['regtimeout']):
            user.quit('Registration timed out')
            continue

    for throttle in iter(throttle for throttle in dict(ircd.throttle) if int(time.time()) - ircd.throttle[throttle]['ctime'] > int(ircd.conf['settings']['throttle'].split(':')[1])):
        del ircd.throttle[throttle]
        continue

    ### Check for timed channels status.
    modify_status = {}
    for chan in channels(ircd):
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
            ircd.handle('MODE', '{} {} 0'.format(chan.name, ' '.join(modes)))

    '''
    Checks related to servers
    '''
    # Send out pings
    pingfreq = 60
    valid_servers = iter([server for server in ircd.servers if server.socket and server.hostname])
    for server in iter([server for server in valid_servers if time.time() - server.ping > pingfreq and time.time() * 1000 - server.lastPingSent > pingfreq/2]):
        server.lastPingSent = time.time() * 1000
        #server.lag_measure = server.lastPingSent
        try:
            server._send(':{} PING {} {}'.format(ircd.sid, ircd.hostname, server.hostname))
        except OSError as ex:
            server.quit('Write error: {}'.format(str(ex)))

    # Ping timeouts (only for direct links)
    for server in iter([server for server in valid_servers if time.time() - server.ping >= 120.0]):
        server.quit('Ping timeout: {} seconds'.format(int(time.time() - server.ping)))

    # Registration timeouts
    for server in iter([server for server in ircd.servers if not server.eos and ((server.introducedBy and not server.introducedBy.eos) or server.socket) and time.time() - server.ping >= 10.0]):
        is_silent = False if server.socket else True
        server.quit('Server registration timed out', silent=is_silent)

    # Check for unknown or timed out servers (non-sockets)
    for server in iter([server for server in ircd.servers if not server.socket and server.uplink and server.uplink.socket and time.time() - server.uplink.ping >= 120.0]):
        is_silent = False if server.socket else True
        server.quit('Server uplink ping timed out: {} seconds'.format(int(time.time() - server.uplink.ping)))

    for callable in [callable for callable in ircd.hooks if callable[0].lower() == 'loop']:
        try:
            callable[2](ircd)
        except Exception as ex:
            logging.exception(ex)

    if not os.path.exists('logs'):
        os.mkdir('logs')

    if not os.path.exists('db'):
        os.mkdir('db')



def read_socket(ircd, sock):
    if not hasattr(sock, 'socket'):
        # Client probably repidly disconnected. Possible causes can be ZNC that have not yet accepted new cert.
        #sock.quit('No socket')
        return

    try:
        if sock.cls:
            buffer_len = int(ircd.conf['class'][sock.cls]['sendq']) * 2
        else:
            buffer_len = 8192 if type(sock).__name__ == 'User' else 65536
        try:
            recv = sock.socket.recv(buffer_len).decode('utf-8')

        except UnicodeDecodeError as ex: # Do nothing, skip read.
            logging.debug(f'Unable to read socket {sock}: {ex}')

            #####
            sock.quit('') # Drunk shit, REMOVE THIS!!!!!!!!! #####
            #####

            return
        except Exception as ex:
            #logging.exception(ex)
            sock.quit('Read error: {}'.format(ex))
            return

        if not recv:
            #logging.error('No data received from {}'.format(sock))
            sock.quit('Read error')
            return

        sock.recvbuffer += recv
        check_flood(ircd, sock)
        sock.handle_recv()
        return recv
    except Exception as ex:
        logging.exception(ex)