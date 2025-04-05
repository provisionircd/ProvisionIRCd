"""
/names command
"""

from handle.core import IRCD, Command, Numeric, Capability, Isupport


def format_name(client, channel, user):
    prefix = channel.get_membermodes_sorted(client=user, prefix=1, reverse=1)
    if prefix and not client.has_capability("multi-prefix"):
        prefix = prefix[0]

    formatted = prefix + user.name

    if client.has_capability("userhost-in-names"):
        formatted += f"!{user.user.username}@{user.user.host}"

    return formatted


def cmd_names(client, recv):
    if not (channel := IRCD.find_channel(recv[1])):
        return client.sendnumeric(Numeric.RPL_ENDOFNAMES, recv[1])

    if 's' in channel.modes and (not channel.find_member(client) and not client.has_permission("channel:see:names:secret")):
        return client.sendnumeric(Numeric.RPL_ENDOFNAMES, recv[1])

    users = []
    for names_client in channel.member_by_client:
        if ('i' in names_client.user.modes and
                (not channel.find_member(client)
                 and not client.has_permission("channel:see:names:invisible"))):
            continue

        if not channel.user_can_see_member(client, names_client):
            continue

        if names_client not in channel.seen_dict[client]:
            channel.seen_dict[client].append(names_client)

        users.append(format_name(client, channel, names_client))

        if len(users) >= 24:
            client.sendnumeric(Numeric.RPL_NAMEREPLY, channel.name, ' '.join(users))
            users = []

    if users:
        client.sendnumeric(Numeric.RPL_NAMEREPLY, channel.name, ' '.join(users))

    client.sendnumeric(Numeric.RPL_ENDOFNAMES, channel.name)


def init(module):
    Capability.add("userhost-in-names")
    Capability.add("multi-prefix")
    Command.add(module, cmd_names, "NAMES", 1)
    Isupport.add("NAMESX")
    Isupport.add("UHNAMES")
