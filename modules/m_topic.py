"""
/topic command
"""

from time import time

from handle.core import Isupport, IRCD, Command, Numeric, Hook
from handle.logger import logging

TOPICLEN = 350


def send_topic(client, channel):
    data = f":{client.fullmask} TOPIC {channel.name} :{channel.topic}"
    channel.broadcast(client, data)

    if channel.name[0] != '&':
        data = f":{client.id} TOPIC {channel.name} {channel.topic_author} {channel.topic_time} :{channel.topic}"
        IRCD.send_to_servers(client, mtags=client.mtags, data=data)


def local_topic_win(client, local_topic, remote_topic):
    our_score = sum(ord(char) for char in local_topic)
    their_score = sum(ord(char) for char in remote_topic)

    if our_score == their_score:
        return 1 if IRCD.me.name < (client.name if client.server else client.uplink.name) else 0

    return 1 if our_score > their_score else 0


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

        topic_text = ' '.join(recv[4:]).removeprefix(':')
        recv_topic_older = 1 if not channel.topic_time or int(recv[3]) < channel.topic_time else 0
        remote_chan_older = 1 if 0 < channel.remote_creationtime < channel.local_creationtime else 0
        same_ts = 1 if channel.local_creationtime == channel.remote_creationtime else 0

        local_win = local_topic_win(client, channel.topic, topic_text)
        if channel.topic and same_ts and int(recv[3]) == channel.topic_time and local_win:
            return

        """
        If a remote channel is older, then that topic will always win.
        If the timestamps are equal, the winner will be determined
        by the outcome of local_topic_win().
        """

        update_topic = 0
        if not channel.topic:
            update_topic = 1
        elif channel.topic != topic_text and channel.topic_time != int(recv[3]):
            if client.uplink.server.synced:
                update_topic = 1
            elif remote_chan_older:
                update_topic = 1
            elif same_ts and recv_topic_older and not local_win:
                update_topic = 1

        if update_topic:
            channel.topic = topic_text
            channel.topic_author, channel.topic_time = recv[2], int(recv[3])
            send_topic(client, channel)
        return

    if not (channel := IRCD.find_channel(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv[1])

    if len(recv) < 3:
        if not channel.topic:
            return client.sendnumeric(Numeric.RPL_NOTOPIC, channel.name)

        client.sendnumeric(Numeric.RPL_TOPIC, channel.name, channel.topic)
        client.sendnumeric(Numeric.RPL_TOPICWHOTIME, channel.name, channel.topic_author, channel.topic_time)
        return

    oper_override = 0
    text = ' '.join(recv[2:]).removeprefix(':')
    if not channel.find_member(client):
        if not client.has_permission("channel:override:topic:notinchannel"):
            return client.sendnumeric(Numeric.ERR_NOTONCHANNEL, channel.name)
        oper_override = 1

    if 't' in channel.modes and client.local and not channel.client_has_membermodes(client, "hoaq"):
        if not client.has_permission("channel:override:topic:no-ops"):
            return client.sendnumeric(Numeric.ERR_CHANOPRIVSNEEDED, channel.name)
        oper_override = 1

    if channel.topic == text:
        return

    h = Hook.call(Hook.PRE_LOCAL_TOPIC, args=(client, channel, text))
    for result, callback in h:
        if result == Hook.DENY:
            return

    channel.topic = text
    channel.topic_author = client.fullmask if text else None
    channel.topic_time = int(time()) if text else 0
    send_topic(client, channel)

    if oper_override and client.user and client.local:
        override_string = f"*** OperOverride by {client.name} ({client.user.username}@{client.user.realhost}) with TOPIC {channel.name} \'{channel.topic}\'"
        IRCD.log(client, "info", "oper", "OPER_OVERRIDE", override_string)

    IRCD.run_hook(Hook.TOPIC, client, channel, channel.topic)


def init(module):
    Command.add(module, cmd_topic, "TOPIC", 1)
    Isupport.add("TOPICLEN", TOPICLEN)
