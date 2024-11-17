"""
/server and /sid command (server)
"""

import re

from handle.core import Flag, Command, Client, IRCD
from classes.errors import Error
from handle.client import make_client, make_server
from handle.logger import logging
from handle.handleLink import (sync_data, start_link_negotiation, broadcast_network_to_new_server,
                               broadcast_new_server_to_network, deny_direct_link)


def auth_incoming_link(client):
    if not client.local.socket:
        logging.error(f"Local client {client.name} does not have a socket?")
        client.exit("Read error: no socket")
        return
    try:
        client.local.socket.getpeername()
        client.local.socket.getsockname()
    except OSError:
        # Closed early.
        return

    if client.name.lower() == IRCD.me.name.lower():
        deny_direct_link(client, Error.SERVER_LINK_NAME_COLLISION, client.name)
        logging.debug(f"Link denied for {client.name}: server names are the same")
        return 0

    if not (link := next((link for link in IRCD.configuration.links if link.name.lower() == client.name.lower()), 0)):
        deny_direct_link(client, Error.SERVER_LINK_NOMATCH)
        logging.debug(f"Link denied for {client.name}: server not found in conf")
        return 0

    if client.local.incoming and not link.incoming_mask:
        deny_direct_link(client, Error.SERVER_LINK_NOMATCH)
        logging.debug(f"Link denied for {client.name}: server not configured as incoming")
        return 0

    class_name = link.connectclass
    client.class_ = IRCD.get_class_from_name(class_name)

    if not client.class_:
        deny_direct_link(client, Error.SERVER_LINK_NOCLASS)
        logging.debug(f"Link denied for {client.name}: unable to assign class to connection")
        return 0

    class_count = len([c.local for c in Client.table if c.local and c.class_ == client.class_])
    if class_count > client.class_.max:
        deny_direct_link(client, Error.SERVER_LINK_MAXCLASS, client.class_.name)
        logging.debug(f"Link denied for {client.name}: max connections for this class")
        return 0

    if client.local.incoming:
        if not link.incoming_mask.is_match(client):
            deny_direct_link(client, Error.SERVER_LINK_NOMATCH_MASK)
            logging.debug(f"Link denied for {client.name}: incoming mask does not match incoming:mask")
            return 0

        client_certfp = client.get_md_value("certfp")

        if link.auth:
            password = link.auth["password"]
            fingerprint = link.auth["fingerprint"]
            cn = link.auth["common-name"]

            if password:
                if client.local.authpass != password:
                    deny_direct_link(client, Error.SERVER_LINK_INCORRECT_PASSWORD)
                    logging.debug(f"[auth] Link denied for {client.name}: incorrect password")
                    return 0
                logging.debug(f"[auth] Incoming link password is a match")

            if fingerprint:
                if not client_certfp or client_certfp != fingerprint:
                    deny_direct_link(client, Error.SERVER_LINK_NOMATCH_CERTFP)
                    logging.debug(f"Link denied for {client.name}: certificate fingerprint mismatch")
                    logging.debug(f"Required: {fingerprint}")
                    logging.debug(f"Received: {client_certfp}")
                    return 0
                logging.debug(f"[auth] Incoming link fingerprint is a match")

            if cn:
                if (client_cn := client.get_md_value(name="certfp_cn")) and client_cn.lower() != cn.lower():
                    deny_direct_link(client, Error.SERVER_LINK_NOMATCH_CN)
                    logging.debug(f"Link denied for {client.name}: certificate Common-Name mismatch")
                    logging.debug(f"Required: {cn}")
                    logging.debug(f"Received: {client_cn}")
                    return 0
                logging.debug(f"[auth] Incoming link CN is a match")

            logging.debug(f"[auth] Incoming server successfully authenticated")
            client.server.link = link
            return 1

        # Deprecated method below.
        if re.match(r"[A-Fa-f0-9]{64}$", link.password):
            """ This link requires a certificate fingerprint """
            if client_certfp and client_certfp == link.password:
                logging.debug(f"Link authenticated by certificate fingerprint")
                client.server.link = link
                return 1
            deny_direct_link(client, Error.SERVER_LINK_NOMATCH_CERTFP)
            logging.debug(f"Link denied for {client.name}: certificate fingerprint mismatch")
            logging.debug(f"Required: {link.password}")
            logging.debug(f"Received: {client_certfp}")
            return 0

        if client.local.authpass != link.password:
            deny_direct_link(client, Error.SERVER_LINK_INCORRECT_PASSWORD)
            logging.debug(f"Link denied for {client.name}: incorrect password")
            return 0

    client.server.link = link
    return 1


def cmd_server(client, recv):
    if not client.local or client.registered or client.exitted:
        return

    logging.debug(f"SERVER from {client.name}: {recv}")

    if len(recv) < 4:
        return client.exit(f"Insufficient SERVER parameters")

    if not client.local.protoctl:
        logging.warning(f"Received SERVER message from {client.name} before PROTOCTL.")
        client.exit("No PROTOCTL message received")
        return

    name = recv[1]
    if (server_exists := IRCD.find_server(name)) and server_exists != client:
        logging.warning(f"[SERVER] Server with name {name} already exists")
        deny_direct_link(client, Error.SERVER_NAME_EXISTS, name)
        return

    client.name = name
    client.hopcount = int(recv[2])

    info = ' '.join(recv[3:])
    if "VL" in client.local.protoctl:
        vl = recv[3].split()[0].removeprefix(':')
        version, flags, num = vl.split('-')
        info = ' '.join(recv[4:])

    info = info.removeprefix(':')
    client.info = info
    if not client.local.authpass:
        return client.exit("Missing password")

    if not auth_incoming_link(client):
        return

    client.server.authed = 1
    logging.info(f"[SERVER] New server: {client.name}. Uplink: {client.uplink.name}, direction: {client.direction.name}")
    if client.local.incoming:
        start_link_negotiation(client)

    broadcast_new_server_to_network(client)
    broadcast_network_to_new_server(client)
    sync_data(client)


def cmd_sid(client, recv):
    logging.debug(F"SID from {client.name}: {recv}")
    name = recv[1]
    hopcount = int(recv[2])
    sid = recv[3]

    if IRCD.find_server(name):
        err_msg = f"Server {name} is already in use on the network"
        client.direct_send(f":{IRCD.me.id} ERROR :{err_msg}")
        client.exit(err_msg)
        return

    if IRCD.find_server(sid):
        client.send([], f"SQUIT {sid} :SID {sid} is already in use on the network")
        return

    if client.local and client.server.link and "nohub" in client.server.link.options:
        logging.warning(f"Server {client.name} is not configured as a hub")
        data = f"SQUIT {sid} :Server {client.name} may not introduce other servers to {IRCD.me.name}"
        logging.warning(f"Sending to {client.name}: {data}")
        client.send([], data)
        return

    info = ' '.join(recv[4:]).removeprefix(':')
    new_server = make_client(direction=client.direction, uplink=client)
    new_server = make_server(new_server)
    new_server.name = name
    new_server.hopcount = hopcount
    new_server.info = info
    new_server.id = sid
    new_server.ip = client.ip
    new_server.server.authed = 1
    logging.info(f"[SID] New server added to the network: {new_server.name} ({new_server.info})")
    logging.info(f"[SID] SID: {new_server.id}, Hopcount: {new_server.hopcount}")
    logging.info(f"[SID] Direction: {new_server.direction.name} ({new_server.direction.id}), Uplink: {new_server.uplink.name} ({new_server.uplink.id})")

    data = f":{client.id} SID {new_server.name} {new_server.hopcount + 1} {new_server.id} :{new_server.info}"
    IRCD.send_to_servers(client, mtags=[], data=data)


def init(module):
    Command.add(module, cmd_server, "SERVER", 3, Flag.CMD_SERVER)
    Command.add(module, cmd_sid, "SID", 4, Flag.CMD_SERVER)
