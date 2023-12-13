"""
/topic command
"""

import time

from handle.core import Isupport, IRCD, Command, Numeric, Hook
from handle.logger import logging

TOPICLEN = 350


def send_topic(client, channel):
    data = f":{client.fullmask} TOPIC {channel.name} :{channel.topic}"
    channel.broadcast(client, data)

    if channel.name[0] != '&':
        data = f":{client.id} TOPIC {channel.name} {channel.topic_author} {channel.topic_time} :{channel.topic}"
        IRCD.send_to_servers(client, mtags=client.mtags, data=data)

    client.mtags = []


def cmd_topic(client, recv):
    """
    Syntax: TOPIC <channel> [text]
    Set or request the topic of a channel.
    To request the topic of a channel, use TOPIC <channel> without any text.
    To clear the topic, use TOPIC <channel> :
    """

    if not client.local or client.server:
        # Only change local topic during sync if the remote topic is older.
        # After sync, always allow topic changes from remote servers.
        if not (channel := IRCD.find_channel(recv[1])):
            return logging.error(f"[topic] Unknown channel for topic: {recv[1]}")
        if not channel.topic_time or int(recv[3]) < channel.topic_time or client.uplink.server.synced:
            text = ' '.join(recv[4:]).removeprefix(':')
            channel.topic = text
            channel.topic_author = recv[2]
            channel.topic_time = int(recv[3])
            send_topic(client, channel)
        return

    oper_override = 0

    if not (channel := IRCD.find_channel(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv[1])

    if len(recv) < 3:
        if not channel.topic:
            return client.sendnumeric(Numeric.RPL_NOTOPIC, channel.name)

        client.sendnumeric(Numeric.RPL_TOPIC, channel.name, channel.topic)
        client.sendnumeric(Numeric.RPL_TOPICWHOTIME, channel.name, channel.topic_author, channel.topic_time)

    else:
        text = ' '.join(recv[2:]).removeprefix(':')
        if client not in channel.clients() and not client.has_permission("channel:override:topic:notinchannel"):
            return client.sendnumeric(Numeric.ERR_NOTONCHANNEL, channel.name)

        elif client not in channel.clients():
            oper_override = 1

        if 't' in channel.modes and client.local:
            if not channel.client_has_membermodes(client, "hoaq"):
                if not client.has_permission("channel:override:topic:no-ops"):
                    return client.sendnumeric(Numeric.ERR_CHANOPRIVSNEEDED, channel.name)
                else:
                    oper_override = 1

        if channel.topic == text:
            # Topic is the same. Do nothing.
            return

        h = Hook.call(Hook.PRE_LOCAL_TOPIC, args=(client, channel, text))
        for result, callback in h:
            if result == Hook.DENY:
                return

        channel.topic = text
        channel.topic_author = client.fullmask
        channel.topic_time = int(time.time())
        send_topic(client, channel)

    if oper_override:
        override_string = f"*** OperOverride by {client.name} ({client.user.username}@{client.user.realhost}) with TOPIC {channel.name} \'{channel.topic}\'"
        IRCD.log(client, "info", "oper", "OPER_OVERRIDE", override_string)

    IRCD.run_hook(Hook.TOPIC, client, channel, channel.topic)


def init(module):
    Command.add(module, cmd_topic, "TOPIC", 1)
    Isupport.add("TOPICLEN", TOPICLEN)
