"""
commands /join and /part
"""

from time import time
from handle.core import Flag, Numeric, Isupport, Command, IRCD, Capability, Hook
from handle.functions import logging


def cmd_join(client, recv):
    """
    Syntax: JOIN <channel> [key]
    Joins a given channel with optional [key].
    """

    if recv[1] == '0':
        for channel in client.channels:
            IRCD.new_message(client)
            channel.do_part(client, reason="Leaving all channels")
        return

    pc = 0
    key = None
    override = Flag.CLIENT_USER_SAJOIN in client.flags
    for chan in recv[1].split(',')[:12]:

        IRCD.new_message(client)
        if client.local and int(time()) - client.creationtime > 5:
            client.local.flood_penalty += 10000

        if (channel := IRCD.find_channel(chan)) and channel.find_member(client):
            """
            Client is already on that channel.
            """
            continue

        if not IRCD.is_valid_channelname(chan) and (client.local and not channel):
            client.sendnumeric(Numeric.ERR_FORBIDDENCHANNEL, chan, "Illegal channel name")
            continue

        # Blegh.
        if len(recv) > 2:
            try:
                key = recv[2:][pc]
                pc += 1
            except IndexError:
                pass

        if len(chan) > IRCD.CHANLEN and (client.local and not channel) and not override:
            client.sendnumeric(Numeric.ERR_FORBIDDENCHANNEL, chan, "Channel name too long")
            continue

        if not channel and not override:
            if IRCD.get_setting("onlyopersjoin") and 'o' not in client.user.modes and client.local:
                IRCD.server_notice(client, "*** Channel creation is limited to IRC operators.")
                continue
            channel = IRCD.create_channel(client, chan)

        if client.local and not override:
            if (error := channel.can_join(client, key)) != 0 and type(error) == tuple:
                client.sendnumeric(error, channel.name)
                IRCD.run_hook(Hook.JOIN_FAIL, client, channel, error)
                continue

        channel.do_join(client.mtags, client)

        if client.local:
            if channel.topic_time != 0:
                Command.do(client, "TOPIC", channel.name)

            Command.do(client, "NAMES", channel.name)

        hook = Hook.LOCAL_JOIN if client.local else Hook.REMOTE_JOIN
        IRCD.run_hook(hook, client, channel)
    client.mtags = []


def cmd_part(client, recv):
    """
    Syntax: PART <channel> [reason]
    Parts the given channel with optional [reason].
    """
    IRCD.new_message(client)
    if len(recv) > 2:
        reason = ' '.join(recv[2:])
    else:
        reason = ''

    reason = reason.rstrip().removeprefix(':')

    if (static_part := IRCD.get_setting("static-part")) and not client.has_permission("channel:override:staticpart"):
        reason = static_part

    for chan_name in recv[1].split(','):
        IRCD.new_message(client)
        if client.local and (int(time()) - client.creationtime) > 5:
            client.local.flood_penalty += 10000

        channel = IRCD.find_channel(chan_name)
        if not channel or not channel.find_member(client):
            client.sendnumeric(Numeric.ERR_NOTONCHANNEL, chan_name)
            continue

        h = Hook.call(Hook.PRE_LOCAL_PART, args=(client, channel, reason))
        for result, callback in h:
            if result:
                reason = result

        channel.do_part(client, reason)

        hook = Hook.LOCAL_PART if client.local else Hook.REMOTE_PART
        IRCD.run_hook(hook, client, channel, reason)
    client.mtags = []


def init(module):
    # Other modules also require this information, like /privmsg and /notice
    Command.add(module, cmd_join, "JOIN", 1, Flag.CMD_USER)
    Command.add(module, cmd_part, "PART", 1, Flag.CMD_USER)
    Isupport.add("CHANTYPES", IRCD.CHANPREFIXES)
    Isupport.add("CHANNELLEN", IRCD.CHANLEN)
    Capability.add("extended-join")
