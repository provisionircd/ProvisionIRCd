"""
/nick command
"""

from time import time
from collections import defaultdict, deque

from handle.core import IRCD, Client, Command, Flag, Numeric, Isupport, Hook
from classes.errors import Error
from handle.client import make_client, make_user
from handle.functions import base64_to_ip
from classes.conf_entries import ConnectClass, Operclass
from handle.logger import logging

nick_flood = defaultdict(lambda: deque(maxlen=50))


def broadcast_nickchange(client, newnick):
    if client.local:
        client.local.flood_penalty += 10_000

    client.send(mtags=client.mtags, data=f":{client.name} NICK :{newnick}")
    IRCD.send_to_local_common_chans(client, mtags=client.mtags, client_cap=None, data=f":{client.fullmask} NICK :{newnick}")
    IRCD.send_to_servers(client, mtags=client.mtags, data=f":{client.id} NICK {newnick} {int(time())}")


def expired_nickflood():
    current_time = int(time())
    expiry_seconds = int(IRCD.get_setting("nickflood").split(':')[1])

    for client, timestamps in list(nick_flood.items()):
        while timestamps and current_time - timestamps[0] >= expiry_seconds:
            timestamps.popleft()
        if not timestamps:
            del nick_flood[client]


def cmd_nick_local(client, recv):
    if not (newnick := recv[1].strip().removeprefix(':')):
        return client.sendnumeric(Numeric.ERR_NONICKNAMEGIVEN)

    if newnick[0].isdigit() or newnick.lower() in ["irc", "ircd", "provisionircd", "server", "network"]:
        return client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, newnick, newnick[0] if newnick[0].isdigit() else newnick)

    if (nickban := IRCD.is_ban_client("nick", client, newnick)) and not client.has_permission("immune:ban"):
        return client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, newnick, nickban.reason)

    newnick = newnick[:IRCD.NICKLEN]
    if any(c.lower() not in IRCD.NICKCHARS for c in newnick):
        invalid_char = next(c for c in newnick if c.lower() not in IRCD.NICKCHARS)
        return client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, newnick, invalid_char)

    if not client.has_permission("immune:nick-flood") and not client.has_flag(Flag.CLIENT_USER_SANICK):
        max_changes = int(IRCD.get_setting("nickflood").split(':')[0])
        if len(nick_flood[client]) >= max_changes:
            client.local.flood_penalty += 25_000
            return client.sendnumeric(Numeric.ERR_NICKTOOFAST, newnick)

    in_use = IRCD.find_client(newnick)
    if in_use and newnick == client.name:
        return

    if in_use and newnick.lower() != client.name.lower():
        return client.sendnumeric(Numeric.ERR_NICKNAMEINUSE, newnick)

    if client.name == '*':
        client.name = newnick
        if client.handshake_finished():
            client.register_user()
        return

    for result, callback in Hook.call(Hook.PRE_LOCAL_NICKCHANGE, args=(client, newnick)):
        if result == Hook.DENY:
            return
        if result == Hook.ALLOW:
            break

    if client.registered:
        nick_flood[client].append(int(time()))

        if client.local and not client.has_flag(Flag.CLIENT_USER_SANICK):
            msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) has changed their nickname to {newnick}"
            IRCD.log(client, "info", "nick", "LOCAL_NICK_CHANGE", msg, sync=0)

        IRCD.new_message(client)
        broadcast_nickchange(client, newnick)
        IRCD.run_hook(Hook.LOCAL_NICKCHANGE, client, newnick)

    client.name = newnick


@logging.client_context
def cmd_nick(client, recv):
    """
    Changes your nickname.
    Users you share a channel with will be notified of this change.
    Syntax: NICK <newnick>
    """

    if client.local:
        cmd_nick_local(client, recv)
    else:
        cmd_nick_remote(client, recv)


def cmd_nick_remote(client, recv):
    newnick = str(recv[1]).strip().removeprefix(':')
    broadcast_nickchange(client, newnick)
    msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) has changed their nickname to {newnick}"
    IRCD.log(client, "info", "nick", "REMOTE_NICK_CHANGE", msg)
    IRCD.run_hook(Hook.REMOTE_NICKCHANGE, client, newnick)
    client.name = newnick


def create_user_from_uid(client, info: list):
    if len(info) < 13:
        return Error.USER_UID_NOT_ENOUGH_PARAMS

    if not (signon := info[3]).isdigit():
        return Error.USER_UID_SIGNON_NO_DIGIT

    if IRCD.find_client(info[6]):
        return Error.USER_UID_ALREADY_IN_USE

    new_client = make_client(direction=client.direction, uplink=client)
    new_client = make_user(new_client)
    new_client.name = info[1]
    new_client.creationtime = int(signon)
    new_client.user.username = info[4]
    new_client.user.realhost = info[5]
    new_client.id = info[6]
    IRCD.client_by_id[new_client.id.lower()] = new_client
    new_client.user.account = info[7]
    new_client.user.modes = info[8].replace('+', '')
    vhost = info[9]
    new_client.user.vhost = vhost if vhost != '*' else new_client.user.realhost
    cloakhost = info[10]
    new_client.user.cloakhost = cloakhost if cloakhost != '*' else new_client.user.realhost

    ip = info[11]
    new_client.ip = base64_to_ip(ip) if ip != '*' and not ip.replace('.', '').isdigit() else (ip if ip != '*' else client.ip)

    new_client.info = ' '.join(info[12:]).removeprefix(':')

    new_client.add_flag(Flag.CLIENT_REGISTERED)
    # logging.debug(f"New remote user {new_client.name}. Uplink: {new_client.uplink.name}, direction: {new_client.direction.name}")
    return new_client


def set_s2s_md(server, client):
    for tag in server.recv_mtags:
        if tag.string.split('=')[0].split('/')[0] != "s2s-md":
            continue

        tag_value = tag.string.split('=')[1]
        md_name = tag.name.split('/')[1]

        client.add_md(md_name, tag_value)

        if md_name == "class":
            client.class_ = ConnectClass(name=tag_value, recvq=0, sendq=0, maxc=0)
        elif md_name == "operclass":
            client.user.operclass = Operclass(name=tag_value, permissions=[])


def nick_collision(client, nick, remote_time):
    for local_client in (c for c in IRCD.get_clients(local=1, user=1) if c.name.lower() == nick.lower()):
        if int(remote_time) <= int(local_client.creationtime) or client.is_uline():
            local_client.add_flag(Flag.CLIENT_NICK_COLLISION)
            local_client.kill("Nick Collision")
        else:
            return 1
    return 0


@logging.client_context
def cmd_uid(client, recv):
    nick = recv[1]
    signon = recv[3]

    if nick_collision(client, nick, int(recv[3])):
        return

    if (new_client := create_user_from_uid(client, recv)) and isinstance(new_client, Client):
        if client.recv_mtags:
            set_s2s_md(client, new_client)
        IRCD.global_user_count += 1
        if IRCD.global_user_count > IRCD.maxgusers:
            IRCD.maxgusers = IRCD.global_user_count
        new_client.sync(cause="cmd_uid()")

    else:
        error_messages = {
            Error.USER_UID_NOT_ENOUGH_PARAMS: Error.send(new_client, client.name, len(recv)),
            Error.USER_UID_ALREADY_IN_USE: Error.send(new_client, recv[6]),
            Error.USER_UID_SIGNON_NO_DIGIT: Error.send(new_client, signon),
        }
        errmsg = error_messages.get(new_client, f"Unknown error: {new_client}")

        if errmsg:
            IRCD.send_to_one_server(client, [], f"SQUIT {IRCD.me.id} {errmsg}")
            client.exit(errmsg)
            data = f"Unable to link with {client.name}: {errmsg}"
            IRCD.log(client, "error", "link", "LINK_FAILED_UID", data, sync=1)
        return

    # logging.debug(f"[UID] Remote client {client.name} server synced: {client.server.synced}")
    # logging.debug(f"Remote client server: {client.uplink.name} (synced: {client.server.synced})")

    if client.server.synced and not client.is_uline():
        msg = (f"*** Client connecting: {new_client.name} ({new_client.user.username}@{new_client.user.realhost}) [{new_client.ip}] "
               f"{new_client.get_ext_info()}")
        IRCD.log(client, "info", "connect", "REMOTE_USER_CONNECT", msg, sync=0)

    IRCD.run_hook(Hook.REMOTE_CONNECT, new_client)


def init(module):
    IRCD.NICKLEN = 24
    Hook.add(Hook.LOOP, expired_nickflood)
    Command.add(module, cmd_nick, "NICK", 1, Flag.CMD_UNKNOWN)
    Command.add(module, cmd_uid, "UID", 12, Flag.CMD_SERVER)
    Isupport.add("NICKLEN", IRCD.NICKLEN)
