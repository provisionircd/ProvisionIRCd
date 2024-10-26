"""
/names command
"""

from handle.core import Numeric, Command, IRCD, Capability, Isupport


def cmd_names(client, recv):
    if not (channel := IRCD.find_channel(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv[1])

    if not channel.find_member(client) and not client.has_permission("channel:see:names"):
        client.sendnumeric(Numeric.RPL_ENDOFNAMES, channel.name)
        return

    users = []
    for names_client in channel.member_by_client:
        if 'i' in names_client.user.modes and (not channel.find_member(names_client) and not client.has_permission("channel:see:names")):
            continue

        if not channel.user_can_see_member(client, names_client):
            continue

        if names_client not in channel.seen_dict[client]:
            channel.seen_dict[client].append(names_client)

        prefix = channel.get_prefix_sorted_str(names_client)
        if not client.has_capability("multi-prefix") and prefix:
            prefix = prefix[0]

        string = prefix + names_client.name

        if client.has_capability("userhost-in-names"):
            string += f"!{names_client.user.username}@{names_client.user.cloakhost}"

        users.append(string)

        if len(users) >= 24:
            client.sendnumeric(Numeric.RPL_NAMEREPLY, channel.name, ' '.join(users))
            users = []
            continue

    if users:
        client.sendnumeric(Numeric.RPL_NAMEREPLY, channel.name, ' '.join(users))

    client.sendnumeric(Numeric.RPL_ENDOFNAMES, channel.name)


def init(module):
    Capability.add("userhost-in-names")
    Capability.add("multi-prefix")
    Command.add(module, cmd_names, "NAMES", 1)
    Isupport.add("NAMESX")
    Isupport.add("UHNAMES")
