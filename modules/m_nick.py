"""
/nick command
"""

import time

from handle.core import Flag, Numeric, Isupport, Command, IRCD, Client, Hook
from classes.errors import Error
from handle.client import make_client, make_user
from handle.functions import Base64toIP
from handle.logger import logging
from classes.conf_entries import ConnectClass, Operclass

NICKLEN = 32


def broadcast_nickchange(client, newnick):
    if client.local:
        client.local.flood_penalty += 10_000

    data = f":{client.name} NICK :{newnick}"
    client.send(client.mtags, data)

    data = f":{client.fullmask} NICK :{newnick}"
    IRCD.send_to_local_common_chans(client, mtags=client.mtags, client_cap=None, data=data)

    data = f":{client.id} NICK {newnick} {int(time.time())}"
    IRCD.send_to_servers(client, mtags=client.mtags, data=data)


class Nick:
    """
    Changes your nickname. Users you share a channel with will be notified of this change.
    Syntax: /NICK <newnick>
    """

    flood = {}


def expired_nickflood():
    for user in Nick.flood:
        for nickchg in [nickchg for nickchg in dict(Nick.flood[user])
                        if int(time.time()) - int(nickchg) > int(IRCD.get_setting('nickflood').split(':')[1])]:
            del Nick.flood[user][nickchg]
            continue


def cmd_nick_local(client, recv):
    newnick = str(recv[1]).strip().removeprefix(':')
    if not newnick.strip():
        return client.sendnumeric(Numeric.ERR_NONICKNAMEGIVEN)

    if newnick[0].isdigit():
        return client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, newnick, newnick[0])

    newnick = newnick[:NICKLEN]

    for c in newnick:
        if c.lower() not in IRCD.NICKCHARS:
            return client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, newnick, c)

    if not client.has_permission("immune:nick-flood") and Flag.CLIENT_USER_SANICK not in client.flags:
        if client in Nick.flood and len(Nick.flood[client]) >= int(IRCD.get_setting("nickflood").split(':')[0]):
            client.local.flood_penalty += 25_000
            return client.sendnumeric(Numeric.ERR_NICKTOOFAST, newnick)

    in_use = IRCD.find_user(newnick)
    if in_use and newnick == client.name:
        # Exact nick.
        return

    if in_use and newnick.lower() != client.name.lower():
        return client.sendnumeric(Numeric.ERR_NICKNAMEINUSE, newnick)

    if client.name == '*':
        client.name = newnick
        if client.handshake_finished():
            client.register_user()
        return

    users = [client]
    for channel in client.channels:
        if not client.has_permission("channel:override:no-nick"):
            if 'N' in channel.modes and not channel.client_has_membermodes(client, "q"):
                return client.sendnumeric(Numeric.ERR_NONICKCHANGE, channel.name)

        for broadcast_client in channel.clients():
            if broadcast_client not in users and broadcast_client != client:
                users.append(broadcast_client)

    for result, callback in Hook.call(Hook.PRE_LOCAL_NICKCHANGE, args=(client, newnick)):
        # logging.debug(f"Result of callback {callback}: {result}")
        if result == Hook.DENY:
            return

    if client.registered:
        if client not in Nick.flood:
            Nick.flood[client] = {}
        Nick.flood[client][time.time()] = True
        if client.local and Flag.CLIENT_USER_SANICK not in client.flags:
            msg = f'*** {client.name} ({client.user.username}@{client.user.realhost}) has changed their nickname to {newnick}'
            IRCD.send_snomask(client, 'N', msg)

        IRCD.new_message(client)
        broadcast_nickchange(client, newnick)
        IRCD.run_hook(Hook.LOCAL_NICKCHANGE, client, newnick)

    client.name = newnick


def cmd_nick(client, recv):
    if client.server:
        client.exit("This port is for servers only")
        return

    if client.local:
        cmd_nick_local(client, recv)
    else:
        cmd_nick_remote(client, recv)


def cmd_nick_remote(client, recv):
    newnick = str(recv[1]).strip().removeprefix(':')
    IRCD.run_hook(Hook.REMOTE_NICKCHANGE, client, newnick)
    broadcast_nickchange(client, newnick)
    msg = f'*** {client.name} ({client.user.username}@{client.user.realhost}) has changed their nickname to {newnick}'
    IRCD.send_snomask(client, 'N', msg)
    client.name = newnick


def create_user_from_uid(client, info: list):
    if len(info) < 13:
        return Error.USER_UID_NOT_ENOUGH_PARAMS
    signon = info[3]
    if not signon.isdigit():
        return Error.USER_UID_SIGNON_NO_DIGIT

    new_client = make_client(direction=client.direction, uplink=client)
    new_client = make_user(new_client)
    new_client.name = info[1]
    new_client.creationtime = int(signon)
    new_client.user.username = info[4]
    new_client.user.realhost = info[5]
    new_client.id = info[6]
    logging.debug(F"Remote client {new_client.name} UID set: {new_client.id}")
    existing_uid = [c.name for c in Client.table if c != new_client and c.id == new_client.id]
    if existing_uid:
        logging.warning(f"[WARNING] UID is already in use by clients: {existing_uid}")
    new_client.user.account = info[7]
    new_client.user.modes = info[8].replace('+', '')
    cloakhost = info[10]
    ip = info[11]
    new_client.ip = ip
    if ip != '*' and not ip.replace('.', '').isdigit() and ip is not None:
        new_client.ip = Base64toIP(ip)
    else:
        new_client.ip = ip
    new_client.info = ' '.join(info[12:]).removeprefix(':')
    if cloakhost == '*':
        new_client.user.cloakhost = new_client.user.realhost
    else:
        new_client.user.cloakhost = cloakhost
    if new_client.ip == '*':
        new_client.ip = client.ip

    new_client.add_flag(Flag.CLIENT_REGISTERED)

    logging.debug(f"New remote user {new_client.name}. Uplink: {new_client.uplink.name}, direction: {new_client.direction.name}")

    return new_client


def set_s2s_md(server, client):
    for tag in server.recv_mtags:
        if tag.string.split('=')[0].split('/')[0] != "s2s-md":
            continue
        tag_name, tag_value = tag.string.split('=')
        md_name, md_value = tag.name.split('/')[1], tag_value
        client.add_md(md_name, md_value)
        if md_name == "class":
            client.class_ = ConnectClass(name=md_value, recvq=0, sendq=0, maxc=0)
        if md_name == "operclass":
            client.user.operclass = Operclass(name=md_value, permissions=[])


def cmd_uid(client, recv):
    logging.debug(f"UID from {client.name}: {recv}")
    nick = recv[1]
    signon = recv[3]
    nick_col = 0
    for c in [c for c in IRCD.local_users() if c.name.lower() == nick.lower()]:
        logging.warning(f'[nick_collision] User {c.name} already found on the server')
        localTS = int(c.creationtime)
        remoteTS = int(recv[3])
        if remoteTS <= localTS or client.ulined:
            logging.warning(f'Local user {c.name} disconnected from local server.')
            c.kill("Nick Collision")
            """ Remote wins. """
            nick_col = 1
        else:
            """ Local wins. """
            nick_col = 2

    if nick_col == 2:
        """ Local won, not processing this UID. Remote will kill its local client. """
        return

    # Add new user.
    if (new_client := create_user_from_uid(client, recv)) and isinstance(new_client, Client):
        if client.recv_mtags:
            set_s2s_md(client, new_client)
        IRCD.global_user_count += 1
        if IRCD.global_user_count > IRCD.maxgusers:
            IRCD.maxgusers = IRCD.global_user_count
        new_client.sync(cause="cmd_uid()")
        IRCD.run_hook(Hook.REMOTE_CONNECT, new_client)
    else:
        match new_client:
            case Error.USER_UID_NOT_ENOUGH_PARAMS:
                errmsg = Error.send(new_client, client.name, len(recv))
            case Error.USER_UID_INVALID:
                errmsg = Error.send(new_client, client.name)
            case Error.USER_UID_SIGNON_NO_DIGIT:
                errmsg = Error.send(new_client, signon)
            case _:
                errmsg = f"Unknown error: {new_client}"
        if errmsg:
            client.exit(errmsg)
            IRCD.send_snomask(client, 's', f"Unable to connect to {client.name}: {errmsg}")

    # logging.debug(f"[UID] Remote client {client.name} server synced: {client.server.synced}")
    # logging.debug(f"Remote client server: {client.uplink.name} (synced: {client.server.synced})")

    if client.server.synced and not client.ulined:
        msg = f"*** Client connecting: {new_client.name} ({new_client.user.username}@{new_client.user.realhost}) [{new_client.ip}]{new_client.get_ext_info()}"
        IRCD.log(client, "info", "connect", "REMOTE_USER_CONNECT", msg, sync=0)


def init(module):
    IRCD.NICKLEN = NICKLEN
    Hook.add(Hook.LOOP, expired_nickflood)
    Command.add(module, cmd_nick, "NICK", 1, Flag.CMD_UNKNOWN)
    Command.add(module, cmd_uid, "UID", 12, Flag.CMD_SERVER, Flag.CMD_UNKNOWN)
    Isupport.add("NICKLEN", NICKLEN)
