"""
/server and /sid command (server)
"""

import re
from datetime import datetime
from time import time

from handle.core import Flag, Command, Client, IRCD
from classes.errors import Error
from handle.client import make_client, make_server
from handle.functions import is_match
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
    except:
        # Closed early.
        return

    if client.name.lower() == IRCD.me.name.lower():
        # client.send([], f"SQUIT :Remote server has the same name as us: {IRCD.me.name}")
        deny_direct_link(client, Error.SERVER_LINK_NAME_COLLISION, client.name)
        logging.debug(f"Link denied for {client.name}: server names are the same")
        return 0

    if not (link := next((l for l in IRCD.configuration.links if l.name.lower() == client.name.lower()), 0)):
        # client.send([], f"SQUIT :Remote server does not have a link block matching our name")
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
        # client.send([], f"SQUIT :Remote server was unable to assign a class to our connection")
        deny_direct_link(client, Error.SERVER_LINK_NOCLASS)
        logging.debug(f"Link denied for {client.name}: unable to assign class to connection")
        return 0

    # logging.debug(f"New server {client.name} has been put in class: {client.local.cls.name}")

    class_count = len([c.local for c in Client.table if c.local and c.class_ == client.class_])
    if class_count > client.class_.max:
        # client.send([], f"SQUIT :Remote server reached the max connections for the link class")
        deny_direct_link(client, Error.SERVER_LINK_MAXCLASS, client.class_.name)
        logging.debug(f"Link denied for {client.name}: max connections for this class")
        return 0

    if client.local.incoming:
        mask_match = 0
        for mask in link.incoming_mask:
            if is_match(mask, client.ip):
                mask_match = 1
                break
        if not mask_match:
            deny_direct_link(client, Error.SERVER_LINK_NOMATCH_IP)
            logging.debug(f"Link denied for {client.name}: incoming IP {client.ip} does not incoming:mask for this link.")
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
                if client_certfp != fingerprint:
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
            # client.send([], f"SQUIT :Remote server requires a certificate fingerprint to link")
            deny_direct_link(client, Error.SERVER_LINK_NOMATCH_CERTFP)
            logging.debug(f"Link denied for {client.name}: certificate fingerprint mismatch")
            logging.debug(f"Required: {link.password}")
            logging.debug(f"Received: {client_certfp}")
            # if client.local.incoming:
            #     data = f"Link denied for {client.name}: certificate fingerprint mismatch"
            return 0

        if client.local.authpass != link.password:
            # client.send([], f"SQUIT :Passwords do not match")
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

    if "VL" in client.local.protoctl:
        vl = recv[3].split()[0]
        # logging.debug(f"VL set: {vl}")
        info = ' '.join(recv[3:][1:])
        version, flags, num = vl.split('-')
    else:
        info = ' '.join(recv[3:])

    info = info.removeprefix(':')

    client.info = info
    # logging.debug(f"Server info set: {info}")
    if not client.local.authpass:
        return client.exit("Missing password")

    if not auth_incoming_link(client):
        return

    client.server.authed = 1
    logging.info(f"[SERVER] New server incoming: {client.name}. Uplink: {client.uplink.name}, direction: {client.direction.name}")
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

    if existing := IRCD.find_server(name):
        # Convert timestamp to datetime object
        dt_object = datetime.fromtimestamp(existing.creationtime)

        # Format datetime object to string
        formatted_time = dt_object.strftime("%Y-%m-%d %H:%M:%S")

        time_elapsed = datetime.now() - dt_object

        # Breakdown the difference into days, hours, minutes, and seconds
        days = time_elapsed.days
        hours, remainder = divmod(time_elapsed.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        client.send([], f"SQUIT {name} :Name {name} is already in use on that network")
        logging.warning(f"New server {name} denied because it was already found on the network")
        logging.warning(f"Connect date: {formatted_time}")
        logging.warning(f"Time connected: {days} days, {hours} hours, {minutes} minutes, {seconds} seconds")
        logging.warning(f"Last message received: {int(time()) - existing.local.last_msg_received} seconds ago.")
        logging.warning(f"Uplink: {existing.uplink}")
        logging.warning(f"Uplink EOS: {existing.synced}")
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
    # new_server.add_flag(Flag.CLIENT_REGISTERED)  # Handled by EOS.
    # new_server.server.synced = 1
    new_server.server.authed = 1
    logging.info(f"[SID] New server added to the network: {new_server.name} ({new_server.info})")
    logging.info(f"[SID] SID: {new_server.id}, Hopcount: {new_server.hopcount}")
    logging.info(f"[SID] Direction: {new_server.direction.name} ({new_server.direction.id}), Uplink: {new_server.uplink.name} ({new_server.uplink.id})")

    data = f":{client.id} SID {new_server.name} {new_server.hopcount + 1} {new_server.id} :{new_server.info}"
    IRCD.send_to_servers(client, mtags=[], data=data)


def init(module):
    Command.add(module, cmd_server, "SERVER", 3, Flag.CMD_SERVER)
    Command.add(module, cmd_sid, "SID", 4, Flag.CMD_SERVER)
