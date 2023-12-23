import hashlib
import socket
import time
import select

import OpenSSL

from classes.errors import Error
from handle.client import make_client, make_server
from handle.core import IRCD, Isupport, Client, Channel, Hook, Extban
from handle.logger import logging


def sync_channels(newserver):
    logging.debug(f"Syncing channels to {newserver.name}")
    try:
        for channel in [c for c in IRCD.get_channels() if c.name[0] != '&']:
            modeparams = []
            for mode in channel.modes:
                if param := channel.get_param(mode):
                    modeparams.append(param)

            modeparams = f" {' '.join(modeparams)}" if modeparams else f"{' '.join(modeparams)}"
            memberlist = []

            for client in channel.clients():
                prefix = ''
                for cmode in [cmode for cmode in channel.get_membermodes_sorted() if channel.client_has_membermodes(client, cmode.flag)]:
                    prefix += cmode.sjoin_prefix
                member = prefix + client.id
                memberlist.append(member)
            if memberlist:
                memberlist = ' '.join(memberlist)

            list_entries = []
            for mode in channel.List:
                cmode = IRCD.get_channelmode_by_flag(mode)
                sjoin_prefix = cmode.sjoin_prefix
                for entry in channel.List[mode]:
                    string = ''
                    if "SJSBY" in newserver.local.protoctl:
                        string = f"<{entry.set_time},{entry.set_by}>"

                    if entry.mask.startswith(Extban.symbol):
                        string += sjoin_prefix + Extban.convert_param(entry.mask, convert_to_name=0)
                    else:
                        string += sjoin_prefix + entry.mask

                    list_entries.append(string)
            if list_entries:
                list_entries = ' '.join(list_entries)

            sjoin_list = ''
            if memberlist or list_entries:
                sjoin_list = " :"
            if memberlist:
                sjoin_list += memberlist
            if list_entries:
                sjoin_list += ' ' + list_entries
            data = f"{channel.creationtime} {channel.name} +{channel.modes}{modeparams}{sjoin_list}"
            logging.debug(f"[sync_channels()] Sending SJOIN data: {data}")
            newserver.send([], f":{IRCD.me.id} SJOIN {data}")
            if channel.topic:
                data = f":{IRCD.me.id} TOPIC {channel.name} {channel.topic_author} {channel.topic_time} :{channel.topic}"
                newserver.send([], data)
    except Exception as ex:
        logging.exception(ex)


def broadcast_network_to_new_server(newserver):
    if newserver.exitted:
        return
    logging.debug(f"Broadcasting all our servers to {newserver.name}")
    for server in [s for s in IRCD.global_servers() if s != newserver and s.name and s.id]:  # and s.server.synced]:
        logging.debug(f"Syncing server {server.name} to {newserver.name}")
        data = f":{IRCD.me.id} SID {server.name} {server.hopcount + 1} {server.id} :{server.info}"
        newserver.send([], data)


def broadcast_new_server_to_network(newserver):
    if newserver.exitted:
        return
    logging.debug(f"Broadcasting new server ({newserver.name}) to the rest of the network")
    for server in [c for c in IRCD.local_servers() if c.direction != newserver]:  # and c.server.synced]:
        logging.debug(f"Syncing {newserver.name} to {server.name}")
        data = f":{IRCD.me.id} SID {newserver.name} 2 {newserver.id} :{newserver.info}"
        server.send([], data)


def start_link_negotiation(newserver):
    logging.debug(f"Starting link negotiation to: {newserver.name}")
    link = next((link for link in IRCD.configuration.links if link.name == newserver.name), 0)
    newserver.send([], f"PASS :{link.password}")
    info = []
    for isupport in Isupport.table:
        info.append(isupport.string)
    newserver.send([], f"PROTOCTL EAUTH={IRCD.me.name} SID={IRCD.me.id} {' '.join(info)}")
    newserver.send([], f"PROTOCTL NOQUIT EAUTH SID CLK SJOIN SJOIN2 UMODE2 VL SJ3 SJSBY NICKIP ESVID NEXTBANS EXTSWHOIS TS={int(time.time())} BOOTED={IRCD.boottime}")
    newserver.send([], "PROTOCTL NICKCHARS= CHANNELCHARS=utf8")
    newserver.send([], f"SERVER {IRCD.me.name} 1 :P300B-*-{IRCD.me.id} {IRCD.me.info}")

    IRCD.run_hook(Hook.SERVER_LINK_POST_NEGOTATION, newserver)


def sync_users(newserver):
    logging.debug(f"Syncing all global registered users to {newserver.name}")
    for client in [c for c in IRCD.global_registered_users() if c.direction != newserver and c.registered]:
        logging.debug(f"Syncing user {client.name} (UID: {client.id}) (uplink={client.uplink.name}, direction={client.direction.name}) to {newserver.name}")
        client.sync(server=newserver, cause="sync_users()")


def sync_data(newserver):
    if newserver.exitted:
        return
    if Client.table:
        sync_users(newserver)
    if Channel.table:
        sync_channels(newserver)

    cloakhash = IRCD.get_setting("cloak-key")
    cloakhash = hashlib.md5(cloakhash.encode("utf-8")).hexdigest()
    data = f":{IRCD.me.id} NETINFO {IRCD.maxgusers} {int(time.time())} {IRCD.versionnumber.replace('.', '')} MD5:{cloakhash} {IRCD.boottime} 0 0 :{IRCD.me.info}"
    newserver.send([], data)

    logging.debug(f"We ({IRCD.me.name}) are done syncing to {newserver.name}, sending EOS.")
    newserver.send([], f":{IRCD.me.id} EOS")
    for server_client in [c for c in IRCD.global_servers() if c not in [IRCD.me, newserver] and c.server.synced]:
        newserver.send([], f":{server_client.id} EOS")

    IRCD.run_hook(Hook.SERVER_SYNC, newserver)
    return


def deny_direct_link(client, error: int, *args):
    message = Error.send(error, *args)
    logging.warning(f"[deny_direct_link] {client.name}: {message}")
    data = f":{IRCD.me.id} ERROR :Link with {IRCD.me.name} denied: {message}"
    client.send([], data)
    IRCD.log(IRCD.me, "error", "link", "LINK_DENIED", f"Link with {client.name} denied: {message}", sync=0)
    client.exit(message)


def start_outgoing_link(link, tls=0, auto_connect=0):
    link.auto_connect = auto_connect
    client = None
    host = link.outgoing["host"]
    port = int(link.outgoing["port"])
    try:
        if not host.replace('.', '').isdigit():
            host = socket.gethostbyname(host)

        client = make_client(direction=None, uplink=IRCD.me)
        IRCD.current_link_sync = client
        make_server(client)
        client.server.link = link
        client.local.socket = socket.socket()
        client.local.auto_connect = auto_connect
        client.local.handshake = 1
        client.name = link.name
        client.ip = host
        client.port = port
        if tls and IRCD.default_tlsctx:
            client.local.tls = IRCD.default_tlsctx
            client.local.socket = OpenSSL.SSL.Connection(IRCD.default_tlsctx, socket=client.local.socket)
        if IRCD.use_poll:
            IRCD.poller.register(client.local.socket, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR)
        IRCD.run_hook(Hook.SERVER_LINK_OUT, client)
        try:
            client.local.socket.connect((host, port))
            logging.debug(f"Succesfully connected out: {host}:{port}")
        except Exception as ex:
            client.exit(str(ex))
            # IRCD.log(IRCD.me, "error", "link", "LINK_OUT_FAIL", f"Unable to establish outgoing link to {link.name}: {ex}", sync=0)
            return

        start_link_negotiation(client)

    except Exception as ex:
        logging.exception(ex)
        # Outgoing link timed out or failed.
        if client:
            client.exit(str(ex))
