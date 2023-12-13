"""
/names command
"""

from handle.core import Numeric, Command, IRCD, Capability, Hook
from handle.logger import logging


def cmd_names(client, recv):
    if not (channel := IRCD.find_channel(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv[1])

    if not channel.find_member(client) and not client.has_permission("channel:see:names"):
        return

    users = []
    for member in channel.members:
        names_client = member.client
        if 'i' in names_client.user.modes and (not channel.find_member(names_client) and not client.has_permission("channel:see:names")):
            continue

        if not channel.user_can_see_member(client, names_client):
            continue

        prefix = channel.get_prefix_sorted_str(names_client)
        string = ''
        if client.has_capability("userhost-in-names"):
            string = f"!{names_client.user.username}@{names_client.user.cloakhost}"
        entry = f"{names_client.name}{string}"
        users.append(prefix + '' + entry)
        if len(users) >= 24:
            client.sendnumeric(Numeric.RPL_NAMEREPLY, channel.name, ' '.join(users))
            users = []
            continue

    client.sendnumeric(Numeric.RPL_NAMEREPLY, channel.name, ' '.join(users))
    client.sendnumeric(Numeric.RPL_ENDOFNAMES, channel.name)


def init(module):
    Capability.add("userhost-in-names")
    Command.add(module, cmd_names, "NAMES", 1)
