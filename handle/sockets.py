import socket
from time import time

import select
from OpenSSL import SSL

from handle.client import (find_client_from_socket,
                           make_client, make_server, make_user,
                           find_listen_obj_from_socket)
from handle.core import Client, IRCD, Hook
from handle.functions import logging, fixup_ip6
from modules.m_connect import connect_to

try:
    from modules.m_websockets import websock_tunnel
except ImportError:
    websock_tunnel = 0


def close_socket(sock):
    for method in [lambda: sock.shutdown(sock.SHUT_RDWR), sock.close]:
        try:
            method()
        except:
            pass
    if IRCD.use_poll:
        try:
            IRCD.poller.unregister(sock)
        except:
            pass


def post_accept(conn, client, listen_obj):
    if IRCD.use_poll:
        IRCD.poller.register(conn, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR | select.EPOLLRDNORM | select.EPOLLRDHUP)
    if listen_obj.tls:
        try:
            client.local.socket = SSL.Connection(listen_obj.tlsctx, conn)
            client.local.socket.set_accept_state()
            client.local.socket.do_handshake()

        except:
            msg = "This port is for TLS connections only"
            data = f"ERROR :Closing link: {msg}"
            try:
                conn.sendall(bytes(data + "\r\n", "utf-8"))
            except:
                pass
            try:
                conn.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            client.exit(msg, sockclose=0)
            # Fallback.
            IRCD.run_parallel_function(close_socket, args=(conn,), delay=0.1)
            return

        client.local.tls = listen_obj.tlsctx

    """ Set to non-blocking after handshake """
    client.local.socket.setblocking(0)
    # logging.debug(f"[post_accept()] New client socket set to non-blocking")
    client.local.handshake = 1

    if "servers" in listen_obj.options:
        if IRCD.current_link_sync and IRCD.current_link_sync != client:
            logging.error(f"Denying new incoming link because we are already processing another link.")
            client.exit(f"Already processing a link, try again.")
            data = f"New server client incoming ({client.ip}:{listen_obj.port}) but we are currently already processing an incoming server."
            if IRCD.current_link_sync and IRCD.current_link_sync.ip == client.ip \
                    and IRCD.current_link_sync.port in [int(lis.port) for lis in IRCD.configuration.listen] \
                    and int(time()) == IRCD.current_link_sync.creationtime:
                data += f" Are you connecting to yourself? Make sure the outgoing IP is correct in the '{IRCD.current_link_sync.name}' link block."
                IRCD.log(IRCD.me, "warn", "link", "LINK_IN_FAIL", data, sync=0)
                logging.warning(data)
            return
        make_server(client)
        IRCD.current_link_sync = client
    else:
        make_user(client)
    logging.debug(f"Accepted new socket on {listen_obj.port}: {client.ip} -- fd: {client.local.socket.fileno()}")
    if client.server:
        IRCD.run_hook(Hook.SERVER_LINK_IN, client)
    else:
        # TODO: Check if this causes issues.
        #  It used to be in handle_recv()
        IRCD.run_hook(Hook.NEW_CONNECTION, client)


def accept_socket(sock, listen_obj):
    # logging.debug(f"accept_socket() called.")
    if len(IRCD.unregistered_clients()) >= 100:
        return logging.warning(f"SYN flood - not processing current connection.")
    try:
        conn, addr = sock.accept()
    except OSError as ex:
        return logging.exception(ex)
    client = make_client(direction=None, uplink=IRCD.me)
    client.local.socket = conn
    client.local.listen = listen_obj
    client.last_ping_sent = time() * 1000
    client.local.last_msg_received = int(time())
    client.local.incoming = 1
    client.ip, client.port = addr
    if client.ip[:7] == "::ffff:":
        client.ip = client.ip.replace("::ffff:", '')  # client connected through ipv6 compatible mode -- strip away cruft
    client.ip = fixup_ip6(client.ip)  # make address look safe, e.g. "::1" is invalid but "0::1" is
    IRCD.run_parallel_function(post_accept, args=(conn, client, listen_obj))


def check_ping_timeouts():
    current_time = int(time())
    for client in IRCD.local_clients():
        if client.registered and (current_time - client.local.last_msg_received) >= 120:
            client.exit("Ping timeout", sock_error=1)


def check_invalid_clients():
    for client in list(IRCD.remote_clients()):
        if not IRCD.find_server(client.id[:3]):
            logging.error(f"Invalid user leftover after possible netsplit: {client.name}. UID: {client.id}")
            client.exit("Invalid user")
            if client in Client.table:
                Client.table.remove(client)
                logging.warning(f"[check_invalid_clients()] Client was still in Client.table after .exit().")


def check_freeze():
    now = int(time())
    since_last_activity = now - IRCD.last_activity
    if IRCD.last_activity and since_last_activity > 2:
        logging.warning(f"IRCd froze for {since_last_activity} seconds. Check logs above for possible cause.")
    IRCD.last_activity = now


def autoconnect_links():
    if IRCD.current_link_sync or [c for c in IRCD.global_servers() if not c.server.synced]:
        return

    for link in [link for link in IRCD.configuration.links if (link.outgoing
                                                               and "autoconnect" in link.outgoing_options
                                                               and not IRCD.find_server(link.name)
                                                               and not link.name.lower() == IRCD.me.name.lower())]:
        if int(time()) - link.last_connect_attempt >= 60:
            interval = IRCD.get_random_interval()
            link.last_connect_attempt = int(time()) + interval
            # logging.debug(f"Attempting autoconnect to: {link.name}")
            # logging.debug(f"Next attempt in {interval} seconds (if this connection fails connected).")
            connect_to(IRCD.me, link, auto_connect=1)
            break


def check_reg_timeouts():
    for client in IRCD.global_servers():
        if not client.registered:
            break
    else:
        """ Loop ended normally, so all servers are registered """
        if IRCD.current_link_sync:
            logging.debug(f"[check_reg_timeouts()] current_link_sync for {IRCD.current_link_sync} unset.")
        IRCD.current_link_sync = None

    reg_timeout = int(IRCD.get_setting("regtimeout"))
    current_time = int(time())
    for client in IRCD.unregistered_clients():
        if current_time - client.local.creationtime >= reg_timeout:
            client.exit("Registration timed out")


def throttle_expire():
    if IRCD.get_setting("throttle"):
        throttle_time = int(IRCD.get_setting("throttle").split(':')[1])
        for throttle in [t for t in dict(IRCD.throttle) if int(time()) - IRCD.throttle[t] >= throttle_time]:
            del IRCD.throttle[throttle]


def hostcache_expire():
    current_time = int(time())
    for ip in dict(IRCD.hostcache):
        timestamp, realhost = IRCD.hostcache[ip]
        if current_time - timestamp >= 3600:
            del IRCD.hostcache[ip]


def remove_delayed_connections():
    for delayed_connection in list(IRCD.delayed_connections):
        client, expire, label = delayed_connection
        if time() >= expire:
            IRCD.remove_delay_client(client, label)


def send_pings():
    pingfreq = 90
    current_time = time()
    for client in (c for c in IRCD.local_clients() if c.registered):
        time_since_last_ping = (current_time * 1000 - client.last_ping_sent) / 1000
        if (current_time - client.local.last_msg_received) >= pingfreq and time_since_last_ping > pingfreq / 3:
            data = f"PING :{IRCD.me.name}" if client.user else f":{IRCD.me.id} PING {IRCD.me.name} {client.name}"
            client.send([], data)
            client.last_ping_sent = current_time * 1000


def find_sock_from_fd(fd: int):
    listen_sockets = [listen.sock for listen in IRCD.configuration.listen if listen.listening]
    clients = [client.local.socket for client in Client.table if client.local]
    for sock in listen_sockets + clients:
        if sock.fileno() == fd:
            return sock


def process_client_buffer(client):
    buffer = client.local.temp_recvbuffer
    messages = []
    while 1:
        delimiter_index = buffer.find('\n')
        if delimiter_index == -1:
            # No complete message in buffer yet
            break
        # Extract the message (including the delimiter)
        message = buffer[:delimiter_index + 1]
        # Remove the message from the buffer
        buffer = buffer[delimiter_index + 1:]
        message = message.strip("\r\n")
        messages.append(message)
    client.local.temp_recvbuffer = buffer
    for message in messages:
        post_sockread(client, message)


def post_sockread(client, recv):
    client.local.bytes_received += len(recv)
    client.local.messages_received += 1
    recv_list = recv.split('\n')
    IRCD.run_hook(Hook.PACKET, client, IRCD.me, IRCD.me, recv_list)
    IRCD.run_hook(Hook.POST_SOCKREAD, client, recv)
    recv = '\n'.join(recv_list)
    if not recv.strip():
        return 1

    for line in recv.split('\n'):
        if not line.strip():
            continue

        debug_in = 0 if client.server else 0
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


def process_backbuffer():
    for client in IRCD.local_clients():
        if client.local.recvbuffer:
            client.handle_recv()

        if client.user:
            current_time = time()
            for buffer in [client.local.backbuffer, client.local.sendq_buffer]:
                for entry in list(buffer):
                    tte, _ = entry
                    if current_time >= tte + 1:
                        buffer.remove(entry)


def is_valid_socket(sock):
    try:
        return sock and sock.fileno() > 0
    except Exception:
        return False


def clean_invalid_sockets(listen_sockets, read_clients, write_clients):
    listen_sockets[:] = [sock for sock in listen_sockets if is_valid_socket(sock)]
    read_clients[:] = [sock for sock in read_clients if is_valid_socket(sock)]
    write_clients[:] = [sock for sock in write_clients if is_valid_socket(sock)]


def get_full_recv(client, sock):
    """
    Return values:

    1:  Data read was OK.
    0:  No data was read.
    -1: Closed connection or error.
    """

    while 1:
        try:
            part = sock.recv(4096)
            if not part:
                return -1
            client.local.temp_recvbuffer += part.decode()
        except (SSL.WantReadError, BlockingIOError):
            if client.local.temp_recvbuffer:
                return 1
            else:
                return 0
        except:
            return -1


def handle_connections():
    while IRCD.running:
        try:
            for client in [c for c in list(Client.table) if c.exitted]:
                try:
                    # Rare race condition?
                    Client.table.remove(client)
                except ValueError:
                    pass
            listen_sockets = [listen.sock for listen in IRCD.configuration.listen if listen.listening]
            available_clients = [client for client in IRCD.local_clients() if client.local.socket and client.local.socket.fileno() > 0 and not client.exitted]
            read_clients = [client.local.socket for client in available_clients if client.local.handshake]
            write_clients = [client.local.socket for client in available_clients if client.local.handshake and client.local.sendbuffer]

            if IRCD.use_poll:
                fdVsEvent = IRCD.poller.poll(500)
                for fd, Event in fdVsEvent:
                    # https://stackoverflow.com/a/42612778
                    # logging.debug(f"New event on fd {fd}: {Event}")
                    if Event & select.POLLNVAL:
                        try:
                            IRCD.poller.unregister(fd)
                        except KeyError:
                            pass
                        continue
                    sock = find_sock_from_fd(fd)
                    if not sock:
                        try:
                            IRCD.poller.unregister(fd)
                        except KeyError:
                            pass
                        continue

                    if Event & (select.POLLIN | select.POLLPRI | select.EPOLLRDNORM):
                        # logging.debug(f"POLLIN or POLLPRI or EPOLLRDNORM")
                        if sock in listen_sockets:
                            if not (listen_obj := find_listen_obj_from_socket(sock)):
                                logging.debug(f"Attempting to close socket because no listen_obj found")
                                close_socket(sock)
                                continue
                            accept_socket(sock, listen_obj)
                        else:
                            if not (client := find_client_from_socket(sock)):
                                logging.debug(f"Attempting to close socket because no client object associated with socket")
                                close_socket(sock)
                                continue
                            if not client.local.handshake:
                                # Handshake not finished yet - waiting.
                                continue

                            bytes_read = get_full_recv(client, sock)
                            if bytes_read == -1:
                                client.exit("Read error", sock_error=1)
                                continue
                            elif bytes_read == 0:
                                continue
                            else:
                                process_client_buffer(client)
                        continue

                    if Event & (select.POLLOUT | select.EPOLLOUT):
                        # logging.debug(f"POLLOUT or EPOLLOUT")
                        if not (client := find_client_from_socket(sock)):
                            close_socket(sock)
                            continue

                        sendbuffer = client.local.sendbuffer
                        if client.direct_send(sendbuffer):
                            client.local.sendbuffer = ''

                        if client.exitted or sock.fileno() < 0:
                            continue
                        IRCD.poller.modify(sock, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR | select.EPOLLRDNORM | select.EPOLLRDHUP)

                    elif Event & (select.POLLHUP | select.POLLERR | select.EPOLLRDHUP):
                        if not (client := find_client_from_socket(sock)):
                            close_socket(sock)
                            continue
                        client.exit("Connection closed", sock_error=1)
                        continue

            else:
                try:
                    clean_invalid_sockets(listen_sockets, read_clients, write_clients)
                    read, write, error = select.select(listen_sockets + read_clients, write_clients, listen_sockets + read_clients, 0.5)
                except ValueError:
                    continue
                for sock in read:
                    if sock in listen_sockets:
                        if not (listen_obj := find_listen_obj_from_socket(sock)):
                            close_socket(sock)
                            continue
                        accept_socket(sock, listen_obj)
                        continue
                    else:
                        if not (client := find_client_from_socket(sock)):
                            close_socket(sock)
                            continue

                        bytes_read = get_full_recv(client, sock)
                        if bytes_read == -1:
                            client.exit("Read error", sock_error=1)
                            continue
                        elif bytes_read == 0:
                            continue
                        else:
                            process_client_buffer(client)

                    continue

                for sock in write:
                    if not (client := find_client_from_socket(sock)):
                        close_socket(sock)
                        continue

                    sendbuffer = client.local.sendbuffer
                    if client.direct_send(sendbuffer):
                        client.local.sendbuffer = ''

                for sock in error:
                    if not (client := find_client_from_socket(sock)):
                        close_socket(sock)
                        continue
                    client.exit("Connection closed", sock_error=1)
                    continue

            send_pings()
            check_reg_timeouts()
            process_backbuffer()
            autoconnect_links()
            throttle_expire()
            hostcache_expire()
            remove_delayed_connections()
            check_ping_timeouts()
            check_invalid_clients()
            check_freeze()
            IRCD.run_hook(Hook.LOOP)

        except KeyboardInterrupt:
            logging.info(f"[KeyboardInterrupt] Shutting down ProvisionIRCd.")
            IRCD.running = 0
            exit()

    print(f"Loop broke")
    exit()
