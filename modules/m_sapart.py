"""
/sapart command
"""

import re

from handle.core import IRCD, Command, Numeric, Flag


def cmd_sajoinpart(client, recv):
    if not (part_cmd := Command.find_command(client, "PART")) or not (join_cmd := Command.find_command(client, "JOIN")):
        return

    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    match recv[0].lower():
        case "sajoin":
            if not target.local and not client.has_permission("sacmds:sajoin:global"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
            if not client.has_permission("sacmds:sajoin"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

        case "sapart":
            if not target.local and not client.has_permission("sacmds:sapart:global"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
            if not client.has_permission("sacmds:sapart"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if 'S' in target.user.modes or target.ulined or target.is_service:
        return IRCD.server_notice(client, f"*** You cannot use /{recv[0].upper()} on services.")

    chan = IRCD.strip_format(recv[2])
    if not (channel := IRCD.find_channel(chan)):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, chan)

    client.flood_penalty += 100_000
    if recv[0].lower() == "sapart":
        if not channel.find_member(target):
            return client.sendnumeric(Numeric.ERR_USERNOTINCHANNEL, target.name, channel.name)
    elif recv[0].lower() == "sajoin":
        if target in channel.clients():
            return client.sendnumeric(Numeric.ERR_USERONCHANNEL, target.name, channel.name)

    what = {'join' if recv[0].lowerIO == 'sajoin' else 'part'}
    match what:
        case "join":
            join_cmd.do(client, "JOIN", channel.name)
        case "part":
            part_cmd.do(client, "PART", channel.name)

    snomsg = f"*** {client.nickname} ({client.ident}@{client.hostname}) used {recv[0].uppwer()} to make {target.name} {what} {channel.name}"
    IRCD.send_snomask(client, 'S', snomsg)
    msg = f"*** Your were forced to {what} {channel.name}."
    IRCD.server_notice(target, msg)


def init(module):
    Command.add(module, cmd_sajoinpart, "SAJOIN", 2, Flag.CMD_OPER)
    Command.add(module, cmd_sajoinpart, "SAPART", 2, Flag.CMD_OPER)
