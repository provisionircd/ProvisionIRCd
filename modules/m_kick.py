"""
/kick command
"""

from handle.core import Command, IRCD, Isupport, Flag, Numeric, Hook

from handle.logger import logging

KICKLEN = 312


def client_can_kick_target(client, target_client, channel, reason):
    for result, callback in Hook.call(Hook.CAN_KICK, args=(client, target_client, channel, reason)):
        if result == Hook.DENY:
            return 0
    return 1


def do_kick(client, channel, target_client, reason):
    data = f":{client.fullmask} KICK {channel.name} {target_client.name} :{reason}"
    channel.broadcast(client, data)
    channel.remove_client(target_client)

    hook = Hook.LOCAL_KICK if target_client.local else Hook.REMOTE_KICK
    IRCD.run_hook(hook, client, target_client, channel, reason)

    data = f":{client.id} KICK {channel.name} {target_client.id} :{reason}"
    IRCD.send_to_servers(client, mtags=client.mtags, data=data)
    client.mtags = []


def cmd_kick(client, recv):
    chan = recv[1]
    if not (channel := IRCD.find_channel(chan)):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, chan)

    if len(recv) == 3:
        reason = client.name
    else:
        reason = ' '.join(recv[3:])
    reason = reason[:KICKLEN].removeprefix(":")

    if not (target_client := IRCD.find_user(recv[2])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[2])

    if not channel.find_member(target_client):
        return client.sendnumeric(Numeric.ERR_USERNOTINCHANNEL, target_client.name, channel.name)

    if not client.local:
        do_kick(client, channel, target_client, reason)
        return

    oper_override = 0

    if not client.server:
        if not channel.client_has_membermodes(client, "hoaq") and not client.has_permission("channel:override:kick:no-ops"):
            return client.sendnumeric(Numeric.ERR_CHANOPRIVSNEEDED, channel.name)

        elif not channel.client_has_membermodes(client, "hoaq"):
            oper_override = 1

    if (channel.level(target_client) > channel.level(client) or 'q' in target_client.user.modes) and not client.has_permission("channel:override:kick:protected"):
        return client.sendnumeric(Numeric.ERR_ATTACKDENY, channel.name, target_client.name)

    elif channel.level(target_client) > channel.level(client) or 'q' in target_client.user.modes:
        oper_override = 1

    if 'Q' in channel.modes and channel.level(client) < 5 and not client.has_permission("channel:override:kick:no-kick"):
        return client.sendnumeric(Numeric.ERR_CANNOTDOCOMMAND, channel.name, "KICKs are not permitted in this channel")

    elif 'Q' in channel.modes and not channel.client_has_membermodes(client, "q"):
        oper_override = 1

    if not client_can_kick_target(client, target_client, channel, reason):
        return

    do_kick(client, channel, target_client, reason)

    if oper_override and not client.ulined and client.user:
        msg = f"*** OperOverride by {client.name} ({client.user.username}@{client.user.realhost}) with KICK {channel.name} {target_client.name} ({reason})"
        IRCD.log(client, "info", "oper", "OPER_OVERRIDE", msg, sync=0)


def init(module):
    Command.add(module, cmd_kick, "KICK", 2, Flag.CMD_USER)
    Isupport.add("KICKLEN", KICKLEN)
