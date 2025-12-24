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

import selectors
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

    try:
        ready_keys = IRCD.selector.select(timeout=timeout / 1000.0)

        for key, mask in ready_keys:
            sock = key.fileobj  # key.fileobj is the socket object originally registered
            event_type = 0
            if mask & selectors.EVENT_READ:
                event_type |= SocketEvent.READ
            if mask & selectors.EVENT_WRITE:
                event_type |= SocketEvent.WRITE

            if event_type:
                events.append(SocketEvent(sock, event_type))

    except Exception as ex:
        logging.exception(ex)

    return events


def process_event(event, listen_sockets):
    sock = event.socket
    client = None if sock in listen_sockets else IRCD.find_client(sock)

    if client and client.has_flag(Flag.CLIENT_TLS_HANDSHAKE_PENDING):
        # logging.debug(f"process_event: Handling event for pending TLS client {client.name}")
        if event.has_error:
            logging.warning(f"Socket error during pending TLS handshake for {client.name}. Closing.")
            client.del_flag(Flag.CLIENT_TLS_HANDSHAKE_PENDING)
            client.exit("Socket error during TLS handshake", sock_error=1)
            return

        if event.can_read or event.can_write:
            wrap_result = wrap_socket(client)

            if wrap_result == 0:
                return

            if client.has_flag(Flag.CLIENT_TLS_HANDSHAKE_COMPLETE):
                #  logging.debug(f"TLS handshake completed for {client.name} via process_event. Finalizing setup.")
                client.local.socket.setblocking(0)
                listen_obj = client.local.listen
                if not listen_obj:
                    logging.error(f"Cannot complete post-TLS setup for {client.name}: Missing listen object.")
                    client.exit("Internal server configuration error")
                    return

                # logging.debug(f"Completed deferred setup")
                client_setup_finished(client, listen_obj)

        return

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
        client.direct_send(client.local.sendbuffer)
        if not client.has_flag(Flag.CLIENT_EXIT) and sock.fileno() > 0 and not client.local.sendbuffer:
            try:
                key = IRCD.selector.get_key(client.local.socket)
                current_events = key.events
                # Modify back to only read if we were previously watching write
                if key.events & selectors.EVENT_WRITE:
                    IRCD.selector.modify(client.local.socket, selectors.EVENT_READ, data=client)
            except (KeyError, AttributeError, OSError):
                pass
            except Exception as ex:
                logging.exception(f"Unexpected error modifying socket to read-only for {client.name}: {ex}")


@IRCD.debug_freeze(debug=0)
def wrap_socket(client: Client, starttls=0) -> int:
    """
    Initiates or continues a non-blocking TLS handshake using flags.

    Returns:
        1: Handshake succeeded OR is pending.
        0: Handshake failed immediately and the client was exited.
    """

    client.local.conn.setblocking(0)

    if not client.has_flag(Flag.CLIENT_TLS_HANDSHAKE_PENDING):
        try:
            tlsctx = client.local.listen.tlsctx if client.local.listen else IRCD.default_tls["ctx"]
            tls_sock = SSL.Connection(tlsctx, client.local.conn)
            tls_sock.set_accept_state()
            tls_sock.setblocking(0)
            try:
                IRCD.selector.unregister(client.local.conn)
            except (KeyError, ValueError, OSError):
                pass
        except TypeError:
            # TLS handshake still in progress.
            return 1

        client.local.socket = tls_sock
        client.local.tls = tlsctx
        client.add_flag(Flag.CLIENT_TLS_HANDSHAKE_PENDING)

    event = None
    try:
        client.local.socket.do_handshake()
        client.del_flag(Flag.CLIENT_TLS_HANDSHAKE_PENDING)
        client.add_flag(Flag.CLIENT_TLS_HANDSHAKE_COMPLETE)
        client.add_flag(Flag.CLIENT_TLS_FIRST_READ)
        event = selectors.EVENT_READ

    except (SSL.WantReadError, SSL.WantWriteError) as ex:
        # .add_flag() is redunant here, but keeping it as a safety net anyway.
        client.add_flag(Flag.CLIENT_TLS_HANDSHAKE_PENDING)
        event = selectors.EVENT_READ if isinstance(ex, SSL.WantReadError) else selectors.EVENT_WRITE

    except SSL.Error:
        IRCD.client_by_sock.pop(client.local.socket, None)
        client.local.socket = client.local.conn
        client.local.socket.setblocking(0)
        msg = "This port is for TLS connections only" if not starttls else f"STARTTLS failed: {str(ex) or 'unknown error'}"
        if starttls:
            logging.exception(ex)
            client.sendnumeric(Numeric.ERR_STARTTLS, "STARTTLS failed.")
        client.direct_send(f"ERROR :{msg}")
        client.exit(msg)
        return 0

    try:
        key = IRCD.selector.get_key(client.local.socket)
        if key.events != event:
            IRCD.selector.modify(client.local.socket, event, data=client)
    except KeyError:
        # Not yet registered. Doing now.
        IRCD.client_by_sock[client.local.socket] = client
        IRCD.selector.register(client.local.socket, event, data=client)

    # TLS handshake OK.
    return 1


@IRCD.debug_freeze(debug=1)
def client_setup_finished(client, listen_obj):
    client.local.handshake = 1

    if listen_obj and "servers" in listen_obj.options:
        if IRCD.current_link_sync and IRCD.current_link_sync != client:
            logging.error(f"Denying new incoming link {client.name} during sync.")
            client.exit(f"Already processing a link, try again.")
            return
        make_server(client)
    else:
        make_user(client)

    IRCD.run_hook(Hook.NEW_CONNECTION, client)

    if client.local.socket.fileno() == -1:
        client.exit("Invalid FD")
        return

    logging.debug(f"Accepted socket on {listen_obj.port}: {client.ip} -- fd: {client.local.socket.fileno()}")


@IRCD.debug_freeze(debug=1)
def post_accept(client, listen_obj):
    if client.local.conn:
        client.local.conn.setblocking(0)
    else:
        logging.error(f"post_accept: client.local.conn is None for {client.name}")
        client.exit("Internal server error (no connection object)")
        return

    if listen_obj and listen_obj.tls:
        wrap_result = wrap_socket(client)

        if wrap_result == 0:
            return

        if client.has_flag(Flag.CLIENT_TLS_HANDSHAKE_PENDING):
            # logging.debug(f"TLS handshake pending for {client.name}. Deferring rest of setup.")
            return

    # Non-TLS connection.
    if not (listen_obj and listen_obj.tls):
        try:
            client.local.socket.setblocking(0)
            IRCD.client_by_sock[client.local.socket] = client
            IRCD.selector.register(client.local.socket, selectors.EVENT_READ, data=client)
        except (KeyError, ValueError, OSError) as ex:
            logging.error(f"Failed register plain socket for {client.name}: {ex}")
            client.exit("Socket registration error")
            return
        except Exception as ex:
            logging.exception(f"Unexpected error registering plain socket for {client.name}: {ex}")
            client.exit("Socket registration error")
            return

    try:
        client.local.socket.setblocking(0)
    except Exception:
        pass

    client_setup_finished(client, listen_obj)


@IRCD.debug_freeze(debug=1)
def accept_socket(sock, listen_obj):
    if sum(1 for _ in IRCD.get_clients(registered=0)) >= 100:
        return logging.warning(f"SYN flood - not processing current connection.")

    sock.setblocking(0)
    try:
        conn, addr = sock.accept()
        # conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
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
    client.local.listen = listen_obj
    client.local.incoming = 1
    client.ip, client.port = addr

    if client.ip[:7] == "::ffff:":
        client.ip = client.ip.replace("::ffff:", '')  # client connected through ipv6 compatible mode -- strip away cruft
    client.ip = fixup_ip6(client.ip)  # make address look safe, e.g. "::1" is invalid but "0::1" is

    if not listen_obj and not ipaddress.ip_address(client.ip).is_private:
        client.exit("Connection reset")
        return

    if listen_obj:
        post_accept(client, listen_obj)
        # IRCD.run_parallel_function(post_accept, args=(client, listen_obj))
    else:
        client.local.handshake = 1
        IRCD.command_socket = client.local.socket


@IRCD.debug_freeze
def check_timeouts():
    float_time = time()
    current_time = int(float_time)

    for client in IRCD.get_clients(local=1):
        timeout_seconds = current_time - client.local.last_msg_received
        if client.registered and timeout_seconds >= 120:
            client.exit(f"Ping timeout: {timeout_seconds} seconds", sock_error=1)

    if reg_timeout := IRCD.get_setting("regtimeout"):
        reg_timeout = int(reg_timeout)
        for client in IRCD.get_clients(local=1, registered=0):
            if current_time - client.local.creationtime >= reg_timeout:
                client.exit("Registration timed out")

    for client in list(IRCD.get_clients(local=0)):
        if not IRCD.find_client(client.id[:3]):
            logging.error(f"Invalid user leftover after possible netsplit: {client.name}. UID: {client.id}")
            client.exit("Invalid user")
            if client in Client.table:
                Client.table.remove(client)
                logging.error(f"[check_timeouts()] Client was still in Client.table after .exit().")

    pending_clients = IRCD.pending_close_clients
    for i in range(len(pending_clients) - 1, -1, -1):
        client = pending_clients[i]
        if current_time - client.exit_time >= 0.2:
            client.cleanup()


@IRCD.debug_freeze
def check_freeze():
    now = int(time())
    since_last_activity = now - IRCD.last_activity
    if IRCD.last_activity and since_last_activity > 2:
        logging.warning(f"IRCd froze for {since_last_activity} seconds. Check logs above for possible cause.")
    IRCD.last_activity = now


@IRCD.debug_freeze
def autoconnect_links() -> None:
    if IRCD.current_link_sync or any(IRCD.get_clients(registered=0)):
        return

    current_time = int(time())
    for link in (link for link in IRCD.configuration.links if (link.outgoing
                                                               and "autoconnect" in link.outgoing_options
                                                               and not IRCD.find_client(link.name)
                                                               and link.name.lower() != IRCD.me.name.lower())):

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
            client.send([], f"PING :{IRCD.me.name}" if client.user else f":{IRCD.me.id} PING {IRCD.me.name} {client.name}")
            client.last_ping_sent = current_time * 1000


@IRCD.debug_freeze
def check_hostname_futures():
    def apply_host(client, realhost):
        client.hostname_future = None
        client.user.realhost = realhost
        client.user.cloakhost = client.user.vhost = IRCD.get_cloak(client)
        client.remember["cloakhost"] = client.user.cloakhost
        client.add_flag(Flag.CLIENT_HOST_DONE)
        if client.handshake_finished():
            client.register_user()

    current_time = int(time())
    for client in list(IRCD.get_clients(local=1)):
        if client.hostname_future:
            future = client.hostname_future
            elapsed_time = current_time - client.hostname_future_submit_time
            realhost = client.ip

            if future.done():
                client.hostname_future = None
                cache_info = ''
                client.hostname_future_submit_time = 0
                try:
                    result = future.result()
                    resolved = result[0]
                    if resolved:
                        realhost = resolved
                        if realhost == "localhost" and not ipaddress.ip_address(client.ip).is_private:
                            realhost = client.ip
                        else:
                            IRCD.hostcache[client.ip] = (int(time()) + 3600, realhost)
                            cache_info = ''

                    IRCD.server_notice(client, f"*** Found your hostname: {realhost}{cache_info}")
                    apply_host(client, realhost)

                except Exception as ex:
                    IRCD.server_notice(client, "*** Couldn't resolve your hostname, using IP address instead.")
                    apply_host(client, realhost)

            elif elapsed_time >= 1:
                future.cancel()
                IRCD.server_notice(client, "*** Couldn't resolve your hostname, using IP address instead.")
                apply_host(client, realhost)


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
        client.local.socket.close()
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
            bb = client.local.backbuffer
            while bb and not (current_time < bb[0][0] + 1):
                bb.pop(0)

            sq = client.local.sendq_buffer
            while sq and not (current_time < sq[0][0] + 1):
                sq.pop(0)


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

        if not buffer:
            return -1

        client.local.temp_recvbuffer += ''.join(buffer)
        return 1

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
        remove_delayed_connections, check_freeze, check_hostname_futures
    ]

    while IRCD.running:
        try:
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
            IRCD.selector.close()
            IRCD.kill_parallel_tasks()
            sys.exit(0)
