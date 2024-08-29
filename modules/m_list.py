"""
/list command
"""

from handle.core import IRCD, Command, Isupport, Numeric
from handle.functions import is_match
from time import time


def cmd_list(client, recv):
    """
    List channels on the network.
    Local channels (channels starting with '&') will not be shown unless you are on the same server.
    Some other channels may also not show, depending on the channel modes that are set.
    -
    Syntax: LIST [conditions]
    Optional conditions can be used.
    A few examples:
    LIST >100               Will only show channels with more than 100 users.
    -                       Use < to negate this condition.
    LIST C<`timestamp`      Show channels that have been created before `timestamp`.
    -                       Note that `timestamp` must be a UNIX timestamp.
    LIST T<`timestamp`      Show channels that had their topic set before `timestamp`.
    """

    client.add_flood_penalty(10_000)
    client.sendnumeric(Numeric.RPL_LISTSTART)

    options = recv[1].split(',') if len(recv) >= 2 else []
    minusers = next((opt[1:] for opt in options if opt.startswith(">") and opt[1:].isdigit()), None)
    maxusers = next((opt[1:] for opt in options if opt.startswith("<") and opt[1:].isdigit()), None)
    created_after = next((opt[2:] for opt in options if opt.startswith("C>")), None)
    created_before = next((opt[2:] for opt in options if opt.startswith("C<")), None)
    topic_after = next((opt[2:] for opt in options if opt.startswith("T>")), None)
    topic_before = next((opt[2:] for opt in options if opt.startswith("T<")), None)
    searchmask = next((opt for opt in options if opt[0] in "*!"), None)

    for channel in IRCD.get_channels():
        channel_open_minutes = int(time()) - channel.creationtime
        topic_minutes = int(time()) - channel.topic_time if channel.topic_time else None

        if ((maxusers and channel.membercount >= int(maxusers)) or
                (minusers and channel.membercount <= int(minusers)) or
                (created_before and channel_open_minutes > int(created_before)) or
                (created_after and channel_open_minutes < int(created_after)) or
                (topic_before and topic_minutes and topic_minutes > int(topic_before)) or
                (topic_after and topic_minutes and topic_minutes < int(topic_after))):
            continue

        if searchmask:
            searchmask = searchmask.lower().lstrip('!')
            if (searchmask[0] == '!' and is_match(searchmask, channel.name.lower())) or (
                    searchmask[0] != '!' and not is_match(searchmask, channel.name.lower())):
                continue

        if ('s' in channel.modes or 'p' in channel.modes) and (not channel.find_member(client) and 'o' not in client.user.modes):
            if 'p' in channel.modes:
                client.sendnumeric(Numeric.RPL_LIST, '*', len(channel.users))
            continue

        client.add_flood_penalty(100)
        list_modes = f"[+{channel.modes}]" if channel.modes else ''
        client.sendnumeric(Numeric.RPL_LIST, channel.name, channel.membercount, list_modes, channel.topic)

    client.sendnumeric(Numeric.RPL_LISTEND)


def init(module):
    Command.add(module, cmd_list, "LIST")
    Isupport.add("SAFELIST")
    Isupport.add("ELIST", "CMNTU")
