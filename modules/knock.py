"""
/knock command
"""

from time import time
from handle.core import IRCD, Numeric, Command, Hook

Knocks = {}
KNOCK_EXPIRE = 60


def cmd_knock(client, recv):
    """
    Knock on an invite-only (+i) channel to request an invitation.
    Syntax:     KNOCK <channel>
    """

    if not (channel := IRCD.find_channel(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv[1])

    if client in channel.clients():
        return client.sendnumeric(Numeric.ERR_CANNOTKNOCK, channel.name, "You are already on that channel")

    if 'i' not in channel.modes:
        return client.sendnumeric(Numeric.ERR_CANNOTKNOCK, channel.name, "Channel is not invite only")

    if channel.get_invite(client):
        return client.sendnumeric(Numeric.ERR_CANNOTKNOCK, channel.name, "You have already been invited")

    if channel.is_banned(client) and not channel.is_exempt(client) and not client.has_permission("channel:override:join:ban"):
        return client.sendnumeric(Numeric.ERR_CANNOTKNOCK, channel.name, "You are banned")

    Knocks.setdefault(channel, {})

    if client in Knocks[channel]:
        knock_time = Knocks[channel][client]
        if int(time() < (knock_time + KNOCK_EXPIRE)) and not client.has_permission("immune:knock-flood"):
            if client.local:
                client.add_flood_penalty(25_000)
                client.sendnumeric(Numeric.ERR_CANNOTKNOCK, channel.name, "Please wait before knocking again")
            return

    Knocks[channel][client] = int(time())

    IRCD.new_message(client)
    data = f":{client.fullmask} KNOCK {channel.name}"
    broadcast_users = [c for c in channel.clients() if c.local
                       and (channel.client_has_membermodes(c, "oaq") or c.has_permission("channel:see:knock"))]
    for user in broadcast_users:
        user.send(client.mtags, data)

    IRCD.server_notice(client, f"You have knocked on {channel.name}")
    client.add_flood_penalty(100_000)

    data = f":{client.id} KNOCK {channel.name}"
    IRCD.send_to_servers(client, client.mtags, data)


def knock_delete_join(client, channel, *args):
    Knocks.get(channel, {}).pop(client, None)


def knock_delete_quit(client, channel, *args):
    for c in [c for c in IRCD.get_channels() if client in Knocks.get(c, {})]:
        del Knocks[c][client]


def knock_expire():
    for channel in Knocks:
        Knocks[channel] = {
            client: knock_time
            for client, knock_time in Knocks[channel].items()
            if int(time()) < knock_time + KNOCK_EXPIRE
        }


def init(module):
    Command.add(module, cmd_knock, "KNOCK", 1)
    Hook.add(Hook.LOCAL_QUIT, knock_delete_quit)
    Hook.add(Hook.REMOTE_QUIT, knock_delete_quit)
    Hook.add(Hook.LOCAL_JOIN, knock_delete_join)
    Hook.add(Hook.REMOTE_JOIN, knock_delete_join)
    Hook.add(Hook.LOOP, knock_expire)
