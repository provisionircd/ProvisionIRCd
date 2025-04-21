import hashlib
import socket
import selectors
from time import time

from OpenSSL import SSL

from classes.errors import Error
from handle.client import make_client, make_server
from handle.core import IRCD, Isupport, Hook, Flag
from classes.data import Extban
from handle.logger import logging


def start_link_negotiation(newserver):
    if not (link := IRCD.get_link(name=newserver.name)) or newserver.has_flag(Flag.CLIENT_EXIT):
        newserver.exit("Server exitted abruptly")
        return

    IRCD.current_link_sync = newserver
    logging.debug(f"Starting link negotiation to: {newserver.name}")
    newserver.send([], f"PASS :{link.password}")
    isupport_str = ' '.join(isupport.string for isupport in Isupport.table)
    newserver.send([], f"PROTOCTL EAUTH={IRCD.me.name} SID={IRCD.me.id} BIGLINES")
    newserver.send([], f"PROTOCTL {isupport_str}")
    newserver.send([], f"PROTOCTL NOQUIT EAUTH SID CLK SJOIN SJOIN2 UMODE2 VL SJ3 SJSBY "
                       f"MTAGS NICKIP ESVID NEXTBANS EXTSWHOIS TS={int(time())} BOOTED={IRCD.me.creationtime}")
    newserver.send([], f"PROTOCTL NICKCHARS=utf8 CHANNELCHARS=utf8")
    newserver.send([], f"SERVER {IRCD.me.name} 1 :P300B-*-{IRCD.me.id} {IRCD.me.info}")


def sync_users(newserver):
    if newserver.has_flag(Flag.CLIENT_EXIT):
        return

    for client in [c for c in IRCD.get_clients(user=1, registered=1) if c.direction != newserver]:
        client.sync(server=newserver, cause="sync_users()")


def sync_channels(newserver):
    if newserver.has_flag(Flag.CLIENT_EXIT):
        return

    try:
        for channel in [c for c in IRCD.get_channels() if c.name[0] != '&']:
            modeparams = [channel.get_param(mode) for mode in channel.modes if channel.get_param(mode)]
            modeparams_str = f" {' '.join(modeparams)}" if modeparams else ''
            mode_string = f"+{channel.modes}{modeparams_str} "

            members = []
            for client in channel.clients():
                prefix = ''.join(cmode.sjoin_prefix for cmode in channel.get_membermodes_sorted()
                                 if channel.client_has_membermodes(client, cmode.flag))
                members.append(prefix + client.id)

            list_entries = []
            for mode in channel.List:
                cmode = IRCD.get_channelmode_by_flag(mode)
                for entry in channel.List[mode]:
                    prefix = f"<{entry.set_time},{entry.set_by}>" if "SJSBY" in newserver.local.protoctl else ''

                    if entry.mask.startswith(Extban.symbol):
                        mask = Extban.convert_param(entry.mask, convert_to_name=0)
                    else:
                        mask = entry.mask

                    list_entries.append(prefix + cmode.sjoin_prefix + mask)

            sjoin_items = members + list_entries

            if not sjoin_items:
                newserver.send([], f":{IRCD.me.id} SJOIN {channel.creationtime} {channel.name} {mode_string}")
            else:
                for i in range(0, len(sjoin_items), 20):
                    batch = sjoin_items[i:i + 20]
                    modes = mode_string if i == 0 else ''
                    newserver.send([], f":{IRCD.me.id} SJOIN {channel.creationtime} {channel.name} {modes}:{' '.join(batch)}")

            if channel.topic:
                newserver.send([], f":{IRCD.me.id} TOPIC {channel.name} {channel.topic_author} {channel.topic_time} :{channel.topic}")

            IRCD.run_hook(Hook.SERVER_SJOIN_OUT, newserver, channel)

    except Exception as ex:
        logging.exception(ex)


def sync_data(newserver):
    if newserver.has_flag(Flag.CLIENT_EXIT):
        return

    sync_users(newserver)
    sync_channels(newserver)

    cloakhash = hashlib.md5(IRCD.get_setting("cloak-key").encode("utf-8")).hexdigest()
    data = (f":{IRCD.me.id} NETINFO {IRCD.maxgusers} {int(time())} {IRCD.versionnumber.replace('.', '')} "
            f"MD5:{cloakhash} {IRCD.me.creationtime} 0 0 :{IRCD.me.info}")
    newserver.send([], data)

    IRCD.run_hook(Hook.SERVER_SYNC, newserver)
    logging.debug(f"We ({IRCD.me.name}) are done syncing to {newserver.name}, sending EOS.")
    newserver.send([], f":{IRCD.me.id} EOS")
    for server_client in [c for c in IRCD.get_clients(server=1) if c not in [IRCD.me, newserver]]:
        newserver.send([], f":{server_client.id} EOS")
    IRCD.run_hook(Hook.POST_SERVER_CONNECT, newserver)


def deny_direct_link(client, error: int, *args):
    message = Error.send(error, *args)
    if IRCD.me.name != '*':
        client.direct_send(f":{IRCD.me.id} ERROR :Link with {IRCD.me.name} denied: {message}")
    if client.name != '*':
        IRCD.log(IRCD.me, "error", "link", "LINK_DENIED", f"Link with {client.name} denied: {message}")
    logging.debug(f"[deny_direct_link] {client.name}: {message}")
    client.exit(message)


def start_outgoing_link(link, tls=0, auto_connect=0, starter=None):
    client = None

    try:
        host = link.outgoing["host"]
        port = int(link.outgoing["port"])

        if not host.replace('.', '').isdigit():
            host = socket.gethostbyname(host)

        client = make_client(direction=None, uplink=IRCD.me)
        make_server(client)

        client.server.link = link
        client.local.socket = socket.socket()
        client.server.link.auto_connect = auto_connect
        client.name = link.name
        client.ip = host
        client.port = port

        if tls and IRCD.default_tls["ctx"]:
            client.local.tls = IRCD.default_tls["ctx"]
            client.local.socket = SSL.Connection(IRCD.default_tls["ctx"], socket=client.local.socket)

        IRCD.client_by_sock[client.local.socket] = client

        IRCD.run_hook(Hook.SERVER_LINK_OUT, client)
        try:
            client.local.socket.connect((host, port))
            if tls:
                try:
                    client.local.socket.do_handshake()
                except SSL.WantReadError:
                    # Possibly denied early @ PROTOCTL.
                    pass
                except Exception as ex:
                    logging.exception(ex)

            IRCD.selector.register(client.local.socket, selectors.EVENT_READ, data=client)
            client.local.handshake = 1
            client.local.socket.setblocking(False)
            IRCD.run_hook(Hook.SERVER_LINK_OUT_CONNECTED, client)
            logging.debug(f"Succesfully connected out: {host}:{port}")
            start_link_negotiation(client)

        except BlockingIOError:
            # This is normal on non-blocking socket.
            pass

        except Exception as ex:
            if not isinstance(ex, (TimeoutError, ConnectionRefusedError, PermissionError, OSError)):
                logging.exception(ex)
            elif isinstance(ex, PermissionError):
                logging.error(f"Unable to connect to {host}:{port}: {str(ex)}. Are you firewalled?")
            client.exit(str(ex))
            # if starter.user and not link.auto_connect:
            #     msg = f"Unable to establish outgoing link to {link.name}: {ex}"
            #     IRCD.server_notice(starter, msg)
            return

    except Exception as ex:
        logging.exception(ex)
        if client:
            client.exit(str(ex))
