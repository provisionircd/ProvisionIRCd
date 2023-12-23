"""
/list command
"""

from handle.core import IRCD, Command, Isupport, Numeric
from handle.functions import is_match
from handle.logger import logging
from time import time


def cmd_list(client, recv):
    client.flood_safe_on()
    client.sendnumeric(Numeric.RPL_LISTSTART)
    minusers, maxusers = None, None
    created_before, created_after = None, None
    topic_before, topic_after = None, None
    searchmask = None
    if len(recv) >= 2:
        # /LIST >10,<50
        for option in recv[1].split(','):
            if len(option) < 2:  # Invalid format.
                continue
            if option.startswith('>') and option[1].isdigit():
                minusers = option[1:]
            elif option.startswith('<') and option[1].isdigit():
                maxusers = option[1:]

            if option.startswith('C') and option[1] in '<>':
                if option[1] == '>':
                    created_after = option[2:]
                else:
                    created_before = option[2:]

            if option.startswith('T') and option[1] in '<>':
                if option[1] == '>':
                    topic_after = option[2:]
                else:
                    topic_before = option[2:]

            if option[0] in '*!':
                searchmask = option

    for channel in IRCD.get_channels():
        channel_open_minutes = int(time()) - channel.creationtime
        if maxusers and channel.membercount >= int(maxusers):
            continue
        if minusers and channel.membercount <= int(minusers):
            continue
        if created_before and channel_open_minutes > int(created_before):
            continue
        if created_after and channel_open_minutes < int(created_after):
            continue
        if channel.topic_time:
            topic_minutes = int(time()) - channel.topic_time
            if topic_before and topic_minutes > int(topic_before):
                continue
            if topic_after and topic_minutes < int(topic_after):
                continue

        if searchmask:
            searchmask = searchmask.lower()
            if searchmask[0] == '!':
                searchmask = searchmask[1:]
                if is_match(searchmask, channel.name.lower()):
                    continue
            elif not is_match(searchmask, channel.name.lower()):
                continue

        if ('s' in channel.modes or 'p' in channel.modes) and (not channel.find_member(client) and 'o' not in client.user.modes):
            if 'p' in channel.modes:
                client.sendnumeric(Numeric.RPL_LIST, "*", len(channel.users))
            continue
        else:
            list_modes = ''
            if channel.modes:
                list_modes = "[+" + channel.modes + "]"
            client.sendnumeric(Numeric.RPL_LIST, channel.name, channel.membercount, list_modes, channel.topic)
    client.sendnumeric(Numeric.RPL_LISTEND)
    client.flood_safe_off()


def init(module):
    Command.add(module, cmd_list, "LIST")
    Isupport.add("SAFELIST")
    Isupport.add("ELIST", "CMNTU")
