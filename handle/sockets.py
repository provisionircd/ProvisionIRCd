from time import time
import socket

import select
from OpenSSL import SSL

from handle.client import (find_client_from_socket,
                           make_client, make_server, make_user,
                           find_listen_obj_from_socket)
from handle.core import Client, IRCD, Hook
from handle.functions import logging
from modules.m_connect import connect_to

try:
    from modules.m_websockets import websock_tunnel
except ImportError:
    websock_tunnel = 0


def close_socket(socket):
    try:
        socket.shutdown(socket.SHUT_RDWR)
    except:
        pass
    try:
        socket.shutdown()
    except:
        pass
    if IRCD.use_poll:
        try:
            IRCD.poller.unregister(socket)
        except KeyError:
            pass


def do_tls_handshake(client):
    # I hate this but it "works".
    handshake_start = int(time())
    attempts = 0
    while 1:
        if attempts > 100:
            fail_time = int(time()) - handshake_start
            logging.debug(f"TLS handshake failed after {fail_time} seconds.")
            client.exit("TLS error")
            return
        try:
            client.local.socket.do_handshake()
            break
        except SSL.WantReadError:
            attempts += 1
            select.select([client.local.socket], [], [], 0.1)
        except SSL.WantWriteError:
            attempts += 1
            select.select([], [client.local.socket], [], 0.1)
        except SSL.Error:
            # If handshake fails, close the connection
            client.exit("TLS error")
            return


def post_accept(conn, client, listen_obj):
    logging.debug(f"post_accept() called.")
    if IRCD.use_poll:
        IRCD.poller.register(conn, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR | select.EPOLLRDNORM | select.EPOLLRDHUP)
    if listen_obj.tls:
        try:
            client.local.socket.do_handshake()
        except:
            pass
        client.local.tls = listen_obj.tlsctx
    logging.debug(f"Accepted new socket on {listen_obj.port}: {client.ip} -- fd: {client.local.socket.fileno()}")
    if "servers" in listen_obj.options:
        if IRCD.current_link_sync and IRCD.current_link_sync != client:
            client.exit(f"Already processing a link, try again.")
            data = f"New server client incoming ({client.ip}:{listen_obj.port}) but we are currently already processing an incoming server."
            if IRCD.current_link_sync.ip == client.ip \
                    and IRCD.current_link_sync.port in [int(lis.port) for lis in IRCD.configuration.listen] \
                    and int(time()) == IRCD.current_link_sync.creationtime:
                data += f" Are you connecting to yourself? Make sure the outgoing IP is correct in the '{IRCD.current_link_sync.name}' link block."
                IRCD.log(IRCD.me, "warn", "link", "LINK_IN_FAIL", data, sync=0)
                logging.warning(data)
            return
        IRCD.current_link_sync = client
        make_server(client)
    else:
        make_user(client)
    if client.server:
        IRCD.run_hook(Hook.SERVER_LINK_IN, client)
    client.local.handshake = 1
    try:
        client.local.socket.setblocking(0)
        logging.debug(f"Socket set to non-blocking.")
    except OSError:
        pass


def accept_socket(sock, listen_obj):
    logging.debug(f"accept_socket() called.")
    conn, addr = sock.accept()
    client = make_client(direction=None, uplink=IRCD.me)
    client.local.socket = conn
    client.local.listen = listen_obj
    client.last_ping_sent = time() * 1000
    client.local.last_msg_received = int(time())
    client.local.incoming = 1
    client.ip, client.port = addr
    IRCD.run_parallel_function(post_accept, args=(conn, client, listen_obj))


def check_ping_timeouts():
    for client in list(IRCD.local_clients()):
        if not client.registered:
            continue
        if (int(time()) - client.local.last_msg_received) >= 120:
            client.exit("Ping timeout")


def check_freeze():
    since_last_activity = int(time()) - IRCD.last_activity
    if IRCD.last_activity and since_last_activity > 2:
        logging.warning(f"IRCd froze for {since_last_activity} seconds. Check logs above for possible cause.")
    IRCD.last_activity = int(time())


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
    for client in IRCD.unregistered_clients():
        alive_in_seconds = int(time()) - client.local.creationtime
        if alive_in_seconds >= int(IRCD.get_setting("regtimeout")):
            client.exit("Registration timed out")


def throttle_expire():
    if IRCD.get_setting("throttle"):
        throttle_time = int(IRCD.get_setting("throttle").split(':')[1])
        for throttle in [t for t in dict(IRCD.throttle) if int(time()) - IRCD.throttle[t] >= throttle_time]:
            del IRCD.throttle[throttle]
            continue


def remove_delayed_connections():
    for delayed_connection in list(IRCD.delayed_connections):
        client, expire, label = delayed_connection
        if time() >= expire:
            IRCD.remove_delay_client(client, label)


def send_pings():
    pingfreq = 90
    for client in [c for c in IRCD.local_clients() if c.registered]:
        last_ping_sent_int = int((time() * 1000) - client.last_ping_sent) / 1000
        if (int(time()) - client.local.last_msg_received) >= pingfreq and last_ping_sent_int > pingfreq / 3:
            if client.user:
                data = f"PING :{IRCD.me.name}"
            else:
                data = f":{IRCD.me.id} PING {IRCD.me.name} {client.name}"
            client.send([], data)
            client.last_ping_sent = time() * 1000


def find_sock_from_fd(fd: int):
    listen_sockets = [listen.sock for listen in IRCD.configuration.listen if listen.listening]
    clients = [client.local.socket for client in Client.table if client.local]
    for sock in listen_sockets + clients:
        if sock.fileno() == fd:
            return sock


def post_sockread(client, recv):
    client.local.bytes_received += len(recv)
    client.local.messages_received += 1
    recv_list = recv.split('\n')
    IRCD.run_hook(Hook.PACKET, client, IRCD.me, IRCD.me, recv_list)
    recv = '\n'.join(recv_list)
    if not recv.strip():
        return 1

    for line in recv.split('\n'):
        if not line.strip():
            continue

        # TODO: REMOVE THIS LINE
        debug_out = 0
        if line.split()[0].lower() in ["ping", "pong"] and client.registered:
            debug_out = 0
        if len(line.split()) > 1 and line.split()[1].lower() in ["ping", "pong"] and client.registered:
            debug_out = 0
        if debug_out:
            logging.debug(f"{client.name}[{client.ip}] > {line}")

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
            for entry in list(client.local.backbuffer):
                tte, data = entry
                if time() > tte + 1:
                    client.local.backbuffer.remove(entry)
            for entry in list(client.local.sendq_buffer):
                tte, data = entry
                if time() >= tte + 1:
                    client.local.sendq_buffer.remove(entry)


def handle_connections():
    # if IRCD.forked:
    #     logging.getLogger().removeHandler(IRCDLogger.stream_handler)

    last_debug = 0
    while IRCD.running:
        # if (int(time()) - last_debug) > (3600 / 2):
        #     logging.debug(f"Half-hourly debug print.")
        #     last_debug = int(time())
        try:
            for client in [c for c in list(Client.table) if c.exitted]:
                Client.table.remove(client)
            listen_sockets = [listen.sock for listen in IRCD.configuration.listen if listen.listening]
            available_clients = [client for client in IRCD.local_clients() if client.local.socket and client.local.socket.fileno() > 0 and not client.exitted]
            read_clients = [client.local.socket for client in available_clients if client.local.handshake]
            write_clients = [client.local.socket for client in available_clients if client.local.handshake and client.local.sendbuffer]

            if IRCD.use_poll:
                fdVsEvent = IRCD.poller.poll(1000)
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
                            # IRCD.run_parallel_function(accept_socket, args=(sock, listen_obj))
                            accept_socket(sock, listen_obj)
                        else:
                            if not (client := find_client_from_socket(sock)):
                                logging.debug(f"Attempting to close socket because no client object associated with socket")
                                close_socket(sock)
                                continue
                            if not client.local.handshake:
                                # Handshake not finished yet - waiting.
                                continue
                            recv = ''
                            try:
                                while chunk := sock.recv(4096).decode():
                                    recv += chunk
                            except (SSL.WantReadError, BlockingIOError):
                                pass
                            except Exception as ex:
                                logging.exception(ex)
                                recv = ''
                            if not recv:
                                client.exit("Read error")
                                continue
                            post_sockread(client, recv)
                        continue

                    if Event & (select.POLLOUT | select.EPOLLOUT):
                        if not (client := find_client_from_socket(sock)):
                            close_socket(sock)
                            continue

                        sendbuffer = client.local.sendbuffer
                        client.local.sendbuffer = ''
                        client.direct_send(sendbuffer)
                        # IRCD.run_parallel_function(client.direct_send, args=(sendbuffer,))
                        # logging.debug(f"Setting {sock} flags to read mode")
                        if client.exitted or sock.fileno() < 0:
                            continue
                        IRCD.poller.modify(sock, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR | select.EPOLLRDNORM | select.EPOLLRDHUP)

                    elif Event & (select.POLLHUP | select.POLLERR | select.EPOLLRDHUP):
                        if not (client := find_client_from_socket(sock)):
                            close_socket(sock)
                            continue
                        client.exit("Read error")
                        continue

            else:
                read, write, error = select.select(listen_sockets + read_clients, write_clients, listen_sockets + read_clients, 1)
                for sock in read:
                    if sock in listen_sockets:
                        if not (listen_obj := find_listen_obj_from_socket(sock)):
                            close_socket(sock)
                            continue
                        # IRCD.run_parallel_function(accept_socket, args=(sock, listen_obj))
                        accept_socket(sock, listen_obj)
                        continue
                    else:
                        if not (client := find_client_from_socket(sock)):
                            close_socket(sock)
                            continue
                        recv = ''
                        try:
                            while chunk := sock.recv(4096).decode():
                                recv += chunk
                        except (SSL.WantReadError, BlockingIOError):
                            pass
                        except:
                            recv = ''
                        if not recv:
                            client.exit("Read error")
                            continue
                        post_sockread(client, recv)
                    continue

                for sock in write:
                    if not (client := find_client_from_socket(sock)):
                        close_socket(sock)
                        continue

                    sendbuffer = client.local.sendbuffer
                    client.local.sendbuffer = ''
                    IRCD.run_parallel_function(client.direct_send, args=(sendbuffer,))

                for sock in error:
                    if not (client := find_client_from_socket(sock)):
                        close_socket(sock)
                        continue
                    client.exit("Connection closed")
                    continue

            send_pings()
            check_reg_timeouts()
            process_backbuffer()
            autoconnect_links()
            throttle_expire()
            remove_delayed_connections()
            check_ping_timeouts()
            check_freeze()
            IRCD.run_hook(Hook.LOOP)

        except KeyboardInterrupt:
            logging.info(f"[KeyboardInterrupt] Shutting down ProvisionIRCd.")
            IRCD.running = 0
            exit()

    print(f"Loop broke")
    exit()
