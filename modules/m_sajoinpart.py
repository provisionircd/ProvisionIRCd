"""
/sajoin and /sapart command
"""

from handle.core import IRCD, Command, Numeric, Flag
from handle.logger import logging


def cmd_sajoinpart(client, recv):
    if not (Command.find_command(client, "PART")) or not (Command.find_command(client, "JOIN")):
        return

    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    if client.local:
        match recv[0].lower():
            case "sajoin":
                if not target.local and not client.has_permission("sacmds:sajoin:global"):
                    return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
                if not client.has_permission("sacmds:sajoin:local"):
                    return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

            case "sapart":
                if not target.local and not client.has_permission("sacmds:sapart:global"):
                    return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
                if not client.has_permission("sacmds:sapart:local"):
                    return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

        if 'S' in target.user.modes or target.ulined or target.is_service:
            return IRCD.server_notice(client, f"*** You cannot use /{recv[0].upper()} on services.")

        client.local.flood_penalty += 100000

    chan = IRCD.strip_format(recv[2])
    if not (channel := IRCD.find_channel(chan)):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, chan)

    if channel.name[0] == '&':
        return IRCD.server_notice(client, f"*** You cannot use /{recv[0].upper()} on local channels.")

    if recv[0].lower() == "sapart":
        if target not in channel.clients():
            return client.sendnumeric(Numeric.ERR_USERNOTINCHANNEL, target.name, channel.name)

    elif recv[0].lower() == "sajoin":
        if target in channel.clients():
            return client.sendnumeric(Numeric.ERR_USERONCHANNEL, target.name, channel.name)

    what = "join" if recv[0].lower() == "sajoin" else "part"
    match what:
        case "join":
            if target.local:
                target.add_flag(Flag.CLIENT_USER_SAJOIN)
                Command.do(target, "JOIN", channel.name)
                target.flags.remove(Flag.CLIENT_USER_SAJOIN)
            data = f":{client.id} SAJOIN {target.name} {channel.name}"
            IRCD.send_to_servers(client, [], data)
        case "part":
            if target.local:
                Command.do(target, "PART", channel.name)
            data = f":{client.id} SAPART {target.name} {channel.name}"
            IRCD.send_to_servers(client, [], data)

    rootevent = recv[0].lower()
    event = "LOCAL_" if target.local else "REMOTE_"
    event += rootevent.upper()
    msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) used {recv[0].upper()} to make {target.name} {what} {channel.name}"
    IRCD.log(client, "info", rootevent, event, msg, sync=0)

    if target.local:
        msg = f"*** Your were forced to {what} {channel.name}."
        IRCD.server_notice(target, msg)


def init(module):
    Command.add(module, cmd_sajoinpart, "SAJOIN", 2, Flag.CMD_OPER)
    Command.add(module, cmd_sajoinpart, "SAPART", 2, Flag.CMD_OPER)
