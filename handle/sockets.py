import ipaddress
import logging
import sys
import os
import socket
import typing
from time import time

try:
    # noinspection PyPackageRequirements
    import psutil
except ImportError:
    psutil = None

import select
from OpenSSL import SSL

from handle.client import make_client, make_server, make_user
from handle.core import IRCD, Hook, Numeric, Command, Flag
from handle.client import Client
from handle.functions import logging, fixup_ip6
from modules.m_connect import connect_to


class SocketEvent:
    READ, WRITE, ERROR, CLOSE = 1, 2, 4, 8

    def __init__(self, socket, event_type):
        self.socket = socket
        self.type = event_type
        self.can_read = bool(self.type & self.READ)
        self.can_write = bool(self.type & self.WRITE)
        self.has_error = bool(self.type & self.ERROR or self.type & self.CLOSE)


def wait_for_events(listen_sockets=None, read_sockets=None, write_sockets=None):
    events = []
    timeout = 100  # Timeout in ms.

    if IRCD.poller:
        try:
            for fd, event in IRCD.poller.poll(timeout):
                if not (sock := find_sock_from_fd(fd)):
                    try:
                        IRCD.poller.unregister(fd)
                    except KeyError:
                        """ Already unregistered. """
                        pass
                    except Exception as ex:
                        logging.exception(ex)
                    continue

                event_type = 0
                if event & (select.POLLIN | select.POLLPRI):
                    event_type |= SocketEvent.READ
                if event & select.POLLOUT:
                    event_type |= SocketEvent.WRITE
                if event & (select.POLLHUP | select.POLLERR | select.POLLNVAL | select.EPOLLRDHUP):
                    event_type |= SocketEvent.ERROR

                events.append(SocketEvent(sock, event_type))
        except Exception as ex:
            logging.exception(ex)
    else:
        listen_sockets = listen_sockets or []
        read_sockets = read_sockets or []
        write_sockets = write_sockets or []

        try:
            reads, writes, errors = select.select(listen_sockets + read_sockets,
                                                  write_sockets,
                                                  listen_sockets + read_sockets + write_sockets,
                                                  timeout / 1000.0)

            events.extend(SocketEvent(sock, SocketEvent.READ) for sock in reads)
            events.extend(SocketEvent(sock, SocketEvent.WRITE) for sock in writes)
            events.extend(SocketEvent(sock, SocketEvent.ERROR) for sock in errors)
        except Exception as ex:
            logging.exception(ex)

    return events


def process_event(event, listen_sockets):
    sock = event.socket
    client = None if sock in listen_sockets else IRCD.find_client(sock)

    if event.can_read:
        if sock in listen_sockets:
            if listen_obj := find_listen_obj_from_socket(sock):
                accept_socket(sock, listen_obj)
            else:
                accept_socket(sock, None)
        elif client and client.local.handshake:
            if client.local.tls and client.has_flag(Flag.CLIENT_TLS_FIRST_READ):
                client.del_flag(Flag.CLIENT_TLS_FIRST_READ)
                return

            if (bytes_read := get_full_recv(client, sock)) in (-1, 1):
                # Value 0 is ignored here. Trying to read again later.
                process_client_buffer(client)
                if bytes_read == -1:
                    client.exit("Connection closed", sock_error=1)

    elif event.can_write and client:
        if client.direct_send(client.local.sendbuffer):
            client.local.sendbuffer = ''

        if IRCD.use_poll and not client.has_flag(Flag.CLIENT_EXIT) and sock.fileno() > 0:
            IRCD.poller.modify(sock, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR | select.EPOLLRDHUP)

    if event.has_error:
        process_client_buffer(client)
        message = "Connection closed"
        try:
            if sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR):
                message = "Read error"
        except OSError:
            message = "Bad file descriptor"
        except Exception as ex:
            message = f"Socket error: {repr(ex)}"

        client.exit(message, sock_error=1)
        return


@IRCD.debug_freeze
def wrap_socket(client, starttls=0):
    while client.local.sendbuffer:
        continue

    tlsctx = client.local.listen.tlsctx or IRCD.default_tls["ctx"]
    tls_sock = SSL.Connection(tlsctx, client.local.conn)
    tls_sock.set_accept_state()

    try:
        tls_sock.setblocking(1)
        tls_sock.do_handshake()
    except Exception as ex:
        client.local.handshake = 1
        client.local.socket.setblocking(0)
        msg = "This port is for TLS connections only" if not starttls else f"STARTTLS failed: {str(ex) or 'unknown error'}"
        if starttls:
            logging.exception(ex)
            client.sendnumeric(Numeric.ERR_STARTTLS, "STARTTLS failed.")
        client.direct_send(f"ERROR :{msg}")
        client.exit(msg)
        tls_sock.close()
        return 0

    # Remove plain sock from table.
    old_sock = client.local.socket
    IRCD.client_by_sock.pop(old_sock, None)

    client.local.socket = tls_sock
    sock = client.local.socket
    IRCD.client_by_sock[sock] = client

    client.local.tls = tlsctx
    client.local.socket.setblocking(0)
    client.local.handshake = 1
    client.add_flag(Flag.CLIENT_TLS_FIRST_READ)
    return 1


@IRCD.debug_freeze
def post_accept(client, listen_obj):
    if IRCD.use_poll and client.local.socket and client.local.socket.fileno() > 0:
        try:
            IRCD.poller.register(client.local.socket,
                                 select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR |
                                 select.EPOLLRDNORM | select.EPOLLRDHUP)
        except Exception as ex:
            logging.error(f"Failed to register socket with poller: {ex}")
            client.exit("Socket registration error")
            return

    if listen_obj.tls and not wrap_socket(client):
        return

    """ Set to non-blocking after handshake """
    client.local.socket.setblocking(0)
    client.local.handshake = 1

    if "servers" in listen_obj.options:
        if IRCD.current_link_sync and IRCD.current_link_sync != client:
            logging.error(f"Denying new incoming link because we are already processing another link.")
            client.exit(f"Already processing a link, try again.")

            data = (f"New server client incoming ({client.ip}:{listen_obj.port})but we are currently already "
                    f"processing an incoming server.")
            if (IRCD.current_link_sync
                    and IRCD.current_link_sync.ip == client.ip
                    and IRCD.current_link_sync.port in [int(lis.port) for lis in IRCD.configuration.listen]
                    and int(time()) == IRCD.current_link_sync.creationtime):
                data += (f" Are you connecting to yourself? Make sure the outgoing IP is correct "
                         f"in the '{IRCD.current_link_sync.name}' link block.")

                IRCD.log(IRCD.me, "warn", "link", "LINK_IN_FAIL", data, sync=0)
                logging.warning(data)
            return

        make_server(client)
    else:
        make_user(client)

    IRCD.run_hook(Hook.NEW_CONNECTION, client)

    if client.local.socket.fileno() == -1:
        client.exit("Invalid socket")
        IRCD.close_socket(client.local.socket)
        logging.warning(f"Discarded invalid socket with fileno: {client.local.socket.fileno()}")
        return

    logging.debug(f"Accepted new socket on {listen_obj.port}: {client.ip} -- fd: {client.local.socket.fileno()}")


@IRCD.debug_freeze
def accept_socket(sock, listen_obj):
    if sum(1 for _ in IRCD.get_clients(registered=0)) >= 100:
        return logging.warning(f"SYN flood - not processing current connection.")

    sock.setblocking(0)
    try:
        conn, addr = sock.accept()
        conn.settimeout(1)
    except BlockingIOError:
        return
    except OSError as ex:
        if ex.errno == 9:
            # Bad file descriptor
            return
        logging.exception(ex)
        return

    client = make_client(direction=None, uplink=IRCD.me)
    client.local.socket = client.local.conn = conn
    IRCD.client_by_sock[client.local.socket] = client
    client.local.listen = listen_obj
    client.local.incoming = 1
    client.ip, client.port = addr

    if client.ip[:7] == "::ffff:":
        client.ip = client.ip.replace("::ffff:", '')  # client connected through ipv6 compatible mode -- strip away cruft
    client.ip = fixup_ip6(client.ip)  # make address look safe, e.g. "::1" is invalid but "0::1" is

    if not listen_obj and not ipaddress.ip_address(client.ip).is_private:
        client.exit("Connection reset")
        IRCD.close_socket(sock)
        return

    if listen_obj:
        IRCD.run_parallel_function(post_accept, args=(client, listen_obj))
    else:
        client.local.handshake = 1
        IRCD.command_socket = client.local.socket


@IRCD.debug_freeze
def check_timeouts():
    current_time = int(time())

    for client in IRCD.get_clients(local=1):
        timeout_seconds = current_time - client.local.last_msg_received
        if client.registered and timeout_seconds >= 120:
            client.exit(f"Ping timeout: {timeout_seconds} seconds", sock_error=1)

    if reg_timeout := IRCD.get_setting("regtimeout"):
        reg_timeout = int(reg_timeout)
        for client in [c for c in IRCD.get_clients(local=1, registered=0)]:
            if current_time - client.local.creationtime >= reg_timeout:
                client.exit("Registration timed out")

    for client in list(IRCD.get_clients(local=0)):
        if not IRCD.find_client(client.id[:3]):
            logging.error(f"Invalid user leftover after possible netsplit: {client.name}. UID: {client.id}")
            client.exit("Invalid user")
            if client in Client.table:
                Client.table.remove(client)
                logging.warning(f"[check_timeouts()] Client was still in Client.table after .exit().")

    for sock, timestamp in list(IRCD.kill_socks.items()):
        if current_time - timestamp >= 1:
            try:
                sock.close()
            except OSError:
                pass
            IRCD.kill_socks.pop(sock)


@IRCD.debug_freeze
def check_freeze():
    now = int(time())
    since_last_activity = now - IRCD.last_activity
    if IRCD.last_activity and since_last_activity > 2:
        logging.warning(f"IRCd froze for {since_last_activity} seconds. Check logs above for possible cause.")
    IRCD.last_activity = now


@IRCD.debug_freeze
@IRCD.parallel
def manage_close_wait_sockets():
    """ Close inactive sockets in CLOSE_WAIT state using psutil. """
    try:
        psutil_instance: typing.Any = psutil
        if not (proc := psutil_instance.Process(IRCD.pid)):
            return

        for conn in list([c for c in proc.connections(kind="inet") if c.fd >= 0 and c.status == "CLOSE_WAIT"]):
            try:
                if conn.raddr:
                    continue

                os.close(conn.fd)
                logging.warning(f"Closed orphaned CLOSE_WAIT socket: FD {conn.fd}")
            except Exception as ex:
                logging.error(f"Error handling socket FD {conn.fd}: {ex}")
    except NameError:
        # psutil not installed.
        return
    except Exception as ex:
        logging.exception(ex)


@IRCD.debug_freeze
def autoconnect_links() -> None:
    if IRCD.current_link_sync or any(IRCD.get_clients(registered=0)):
        return

    current_time = int(time())
    for link in [link for link in IRCD.configuration.links if (link.outgoing
                                                               and "autoconnect" in link.outgoing_options
                                                               and not IRCD.find_client(link.name)
                                                               and link.name.lower() != IRCD.me.name.lower())]:

        seconds_since_last_attempt = current_time - link.last_connect_attempt
        if seconds_since_last_attempt >= 10:
            interval = IRCD.get_random_interval(max=300)
            link.last_connect_attempt = current_time + interval
            connect_to(IRCD.me, link, auto_connect=1)
            break


@IRCD.debug_freeze
def throttle_expire() -> None:
    if throttle_setting := IRCD.get_setting("throttle"):
        throttle_time = int(throttle_setting.split(':')[1])
        cutoff_time = int(time()) - throttle_time
        for client_ip in list(IRCD.throttle.keys()):
            timestamps = IRCD.throttle[client_ip]
            while timestamps and timestamps[0] <= cutoff_time:
                timestamps.popleft()
            if not timestamps:
                del IRCD.throttle[client_ip]


@IRCD.debug_freeze
def hostcache_expire() -> None:
    current_time = int(time())
    for ip in dict(IRCD.hostcache):
        dns_ttl, realhost = IRCD.hostcache[ip]
        if current_time >= dns_ttl:
            del IRCD.hostcache[ip]


@IRCD.debug_freeze
def remove_delayed_connections():
    for delayed_connection in list(IRCD.delayed_connections):
        client, expire, label = delayed_connection
        if time() >= expire:
            IRCD.remove_delay_client(client, label)


@IRCD.debug_freeze
def send_pings():
    pingfreq = 90
    current_time = time()
    for client in IRCD.get_clients(local=1, registered=1):
        time_since_last_ping = (current_time * 1000 - client.last_ping_sent) / 1000
        if (current_time - client.local.last_msg_received) >= pingfreq and time_since_last_ping > pingfreq / 3:
            data = f"PING :{IRCD.me.name}" if client.user else f":{IRCD.me.id} PING {IRCD.me.name} {client.name}"
            client.send([], data)
            client.last_ping_sent = current_time * 1000


@IRCD.debug_freeze
def find_sock_from_fd(fd: int):
    # Unfortunately no reliable O(1) lookup possible.
    for sock in (listen.sock for listen in IRCD.configuration.listen if listen.listening):
        if sock.fileno() == fd:
            return sock

    for sock in (client.local.socket for client in Client.table if client.local):
        if sock.fileno() == fd:
            return sock


def find_listen_obj_from_socket(socket):
    return next((listen_obj for listen_obj in IRCD.configuration.listen if listen_obj.sock == socket), None)


@IRCD.debug_freeze
def process_client_buffer(client):
    buffer = client.local.temp_recvbuffer

    if client.local.socket == IRCD.command_socket:
        command = buffer.strip()

        if command == "REHASH":
            Command.do(IRCD.me, "REHASH")
        elif command == "RESTART":
            Command.do(IRCD.me, "RESTART")
        elif command == "SHUTDOWN":
            Command.do(IRCD.me, "DIE")
        IRCD.close_socket(client.local.socket)
        return

    last_newline = buffer.rfind('\n')
    if last_newline != -1:
        complete_data = buffer[:last_newline + 1]
        messages = [line.strip('\r') for line in complete_data.split('\n') if line]
        for message in messages:
            post_sockread(client, message)

    client.local.temp_recvbuffer = buffer[last_newline + 1:]


@IRCD.debug_freeze
def post_sockread(client, recv) -> None:
    client.local.bytes_received += len(recv)
    client.local.messages_received += 1

    recv_list = recv.split('\n')

    IRCD.run_hook(Hook.PACKET, client, IRCD.me, IRCD.me, recv_list)
    IRCD.run_hook(Hook.POST_SOCKREAD, client, recv)

    for line in recv_list:
        if not (line := line.strip()):
            continue

        debug_in = 0
        if client.registered:
            ignore = ["ping", "pong", "privmsg", "notice", "tagmsg", "id", "identify", "auth", "register", "nickserv", "ns"]
            split_line = line.split()
            for i in range(min(3, len(split_line))):
                if split_line[i].lower() in ignore:
                    debug_in = 0
                    break

        if debug_in:
            logging.debug(f"[IN] {client.name}[{client.ip}] > {line}")

        time_to_execute = time()

        if client.user and client.registered:
            if client.local.recvbuffer and client.local.backbuffer:
                """ Backbuffer delay already kicked in (see below), using latest timestamp + 1 """
                time_to_execute = client.local.recvbuffer[-1][0]
                time_to_execute += 1

            if len(client.local.backbuffer) == 10 and 'o' not in client.user.modes:
                """
                When a non-oper user reaches 10 backbuffer entries,
                we will start delaying consecutive recvbuffer entries until the backbuffer is cleared.
                Backbuffer entries are removed after 1 second.
                """
                time_to_execute += 1

            if 'o' not in client.user.modes:
                backbuffer_time = time_to_execute
                """ Keep the backbuffer entry duration based on the incoming data length. """
                delay = len(line) / 10
                backbuffer_time += delay
                client.local.backbuffer.append([backbuffer_time, line])

        client.local.recvbuffer.append([time_to_execute, line])

    client.check_flood()
    client.handle_recv()


@IRCD.debug_freeze
def process_backbuffer() -> None:
    current_time = time()

    for client in IRCD.get_clients(local=1):
        if client.local.recvbuffer:
            client.handle_recv()

        if client.user:
            if client.local.backbuffer:
                client.local.backbuffer = [entry for entry in client.local.backbuffer if current_time < entry[0] + 1]

            if client.local.sendq_buffer:
                client.local.sendq_buffer = [entry for entry in client.local.sendq_buffer if current_time < entry[0] + 1]


@IRCD.debug_freeze
def get_full_recv(client, sock):
    """
    Return values:

    1:  Full data read.
    0:  No data was read yet. Try again later.
    -1: Stream incomplete or connection closed.
    """

    buffer = []

    try:
        while part := sock.recv(4096):
            buffer.append(part.decode())
        client.local.temp_recvbuffer += ''.join(buffer)
        return -1
    except (SSL.WantReadError, BlockingIOError) as ex:
        client.local.temp_recvbuffer += ''.join(buffer)
        return 1 if client.local.temp_recvbuffer else 0

    except SSL.SysCallError as ex:
        if ex.args[0] in (10035, 35):
            logging.error(str(ex))
            client.local.temp_recvbuffer += ''.join(buffer)
            return 1 if client.local.temp_recvbuffer else 0
        return -1

    except (ConnectionResetError, UnicodeDecodeError, SSL.SysCallError, SSL.ZeroReturnError) as ex:
        """ Connection closed while reading. Client exitted. """
        return -1

    except Exception as ex:
        logging.exception(ex)
        return -1


def handle_connections():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind(('', 65432))
        server_socket.listen(10)
    except OSError:
        # Already an instance running.
        server_socket = None

    last_periodic_tasks = int(time())
    task_interval = 1

    periodic_tasks = [
        send_pings, check_timeouts, process_backbuffer,
        autoconnect_links, throttle_expire, hostcache_expire,
        remove_delayed_connections, check_freeze
    ]

    while IRCD.running:
        try:
            for client in [c for c in list(Client.table) if c.has_flag(Flag.CLIENT_EXIT)]:
                try:
                    Client.table.remove(client)
                except ValueError:
                    pass

            listen_sockets = [listen.sock for listen in IRCD.configuration.listen if listen.listening]
            if server_socket:
                listen_sockets.append(server_socket)

            available_clients = [c for c in IRCD.get_clients(local=1)
                                 if c.local.socket and c.local.socket.fileno() > 0 and not c.has_flag(Flag.CLIENT_EXIT)]

            read_clients = []
            write_clients = []
            for client in available_clients:
                if client.local.handshake:
                    read_clients.append(client.local.socket)
                    if client.local.sendbuffer:
                        write_clients.append(client.local.socket)

            events = wait_for_events(listen_sockets=listen_sockets, read_sockets=read_clients, write_sockets=write_clients)
            for event in events:
                process_event(event, listen_sockets)

            current_time = int(time())
            if current_time - last_periodic_tasks >= task_interval:
                last_periodic_tasks = current_time
                for task in periodic_tasks:
                    task()
                IRCD.run_hook(Hook.LOOP)

        except KeyboardInterrupt:
            logging.info(f"[KeyboardInterrupt] Shutting down ProvisionIRCd.")
            IRCD.running = 0
            IRCD.kill_parallel_tasks()
            sys.exit(0)
