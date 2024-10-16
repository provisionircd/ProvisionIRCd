"""
/kick command
"""

from handle.core import Command, IRCD, Isupport, Flag, Numeric, Hook

KICKLEN = 300


def client_can_kick_target(client, target_client, channel, reason, oper_override):
    for result, callback in Hook.call(Hook.CAN_KICK, args=(client, target_client, channel, reason, oper_override)):
        if result == Hook.DENY:
            return 0
    return 1


def do_kick(client, channel, target_client, reason):
    fullmask = IRCD.me.name if client == IRCD.me else client.fullmask

    data = f":{fullmask} KICK {channel.name} {target_client.name} :{reason}"
    channel.broadcast(client, data)
    channel.remove_client(target_client)

    hook = Hook.LOCAL_KICK if target_client.local else Hook.REMOTE_KICK
    IRCD.run_hook(hook, client, target_client, channel, reason)

    data = f":{client.id} KICK {channel.name} {target_client.id} :{reason}"
    IRCD.send_to_servers(client, mtags=client.mtags, data=data)

    if (client.user and client.local and client.registered) or (not client.local and client.uplink.server.synced) and not client.ulined:
        event = "LOCAL_KICK" if client.local else "REMOTE_KICK"
        msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) has kicked {target_client.name} off channel {channel.name}: {reason}"
        IRCD.log(client, "info", "kick", event, msg, sync=0)


def cmd_kick(client, recv):
    """
    Kicks a user from the channel. Requires +h or higher.
    Syntax: KICK <nickname> <reason>
    """

    chan = recv[1]
    if not (channel := IRCD.find_channel(chan)):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, chan)

    reason = client.name if len(recv) == 3 else ' '.join(recv[3:])
    reason = reason[:KICKLEN].removeprefix(':')

    # List, so that modules can change the value.
    oper_override = [0]

    if not client.server:
        if not channel.client_has_membermodes(client, "hoaq") and not client.has_permission("channel:override:kick:no-ops"):
            return client.sendnumeric(Numeric.ERR_CHANOPRIVSNEEDED, channel.name)

        elif not channel.client_has_membermodes(client, "hoaq"):
            oper_override[0] = 1

    for target in recv[2].split(','):
        if not (target_client := IRCD.find_user(target)):
            client.sendnumeric(Numeric.ERR_NOSUCHNICK, target)
            continue

        if not channel.find_member(target_client):
            client.sendnumeric(Numeric.ERR_USERNOTINCHANNEL, target_client.name, channel.name)
            continue

        if client == IRCD.me or not client.local:
            do_kick(client, channel, target_client, reason)
            continue

        if (channel.level(target_client) > channel.level(client) or 'q' in target_client.user.modes) and not client.has_permission("channel:override:kick:protected"):
            client.sendnumeric(Numeric.ERR_ATTACKDENY, channel.name, target_client.name)
            continue

        elif channel.level(target_client) > channel.level(client) or 'q' in target_client.user.modes:
            oper_override[0] = 1

        if not client_can_kick_target(client, target_client, channel, reason, oper_override):
            continue

        do_kick(client, channel, target_client, reason)

        if oper_override[0] and client.user and client.local:
            msg = f"*** OperOverride by {client.name} ({client.user.username}@{client.user.realhost}) with KICK {channel.name} {target_client.name} ({reason})"
            IRCD.log(client, "info", "oper", "OPER_OVERRIDE", msg, sync=1)


def init(module):
    Command.add(module, cmd_kick, "KICK", 2, Flag.CMD_USER)
    Isupport.add("KICKLEN", KICKLEN)
