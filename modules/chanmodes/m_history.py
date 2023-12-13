"""
provides chmode +H (channel message history support)
"""

from time import time
from datetime import datetime

from handle.logger import logging
from handle.core import IRCD, Channelmode, Hook, Batch, MessageTag, Numeric, Command
from handle.validate_conf import conf_error


class Configuration:
    max_lines_registered = 0
    max_lines_unregistered = 0


class ChatHistory:
    backlog = {}

    reply_time = {}

    max_unreg = 10
    max_reg = 10

    BEFORE = 0
    AFTER = 1
    BETWEEN = 2
    AROUND = 3
    LATEST = 4

    def __init__(self, sender, mtags: list, svid, utc_time: float, sendtype: str, data: str):
        self.sender = sender
        self.mtags = mtags
        self.svid = svid
        self.utc_time = utc_time
        self.sendtype = sendtype
        self.data = data

    @property
    def msgid(self):
        return next((t.value for t in self.mtags if t.name == "msgid"), 0)

    @staticmethod
    def add_to_buff(channel, history_obj):
        if channel not in ChatHistory.backlog:
            ChatHistory.backlog[channel] = []
        ChatHistory.backlog[channel].append(history_obj)

    @staticmethod
    def timestr_to_timestamp(utc_timestr: str) -> float:
        try:
            dt = datetime.strptime(utc_timestr, "%Y-%m-%dT%H:%M:%S.%fZ")
            return dt.timestamp()
        except ValueError:
            return 0.0


class HistoryFilter:
    def __init__(self, timestamp_1=None, timestamp_2=None, msgid_1=None, msgid_2=None, limit=0, cmd=None):
        self.timestamp_1 = timestamp_1
        self.timestamp_2 = timestamp_2
        self.msgid_1 = msgid_1
        self.msgid_2 = msgid_2
        self.limit = limit
        self.cmd = cmd


def history_conv_param(param):
    limit = int(param.split(':')[0])
    if limit > 25:
        limit = 25
    expire = int(param.split(':')[1])
    if expire > 10080:
        expire = 10080
    return_param = f"{limit}:{expire}"
    return return_param


def history_validate_param(client, channel, action, mode, param, CHK_TYPE):
    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if channel.client_has_membermodes(client, "oaq"):
            return 1
        return 0

    if CHK_TYPE == Channelmode.CHK_PARAM:
        if len(param.split(':')) < 2:
            return 0
        lines, expire = param.split(':')
        if not lines.isdigit() or not expire.isdigit():
            return 0
        return 1


def send_empty_batch(client, channel):
    if client.has_capability("batch"):
        batch = Batch(started_by=IRCD.me)
        client.send([], data=f":{IRCD.me.name} BATCH +{batch.label} chathistory {channel.name}")
        client.send([], data=f":{IRCD.me.name} BATCH -{batch.label}")


def clear_history_channel_destroy(client, channel):
    if channel in ChatHistory.backlog:
        del ChatHistory.backlog[channel]


def create_history_channel_create(client, channel):
    ChatHistory.backlog[channel] = []


def add_to_historybuf(client, channel, message, sendtype):
    limit = ChatHistory.max_unreg if 'r' not in channel.modes else ChatHistory.max_reg
    if channel not in ChatHistory.backlog:
        ChatHistory.backlog[channel] = []
    while limit and len(ChatHistory.backlog[channel]) >= limit:
        ChatHistory.backlog[channel] = ChatHistory.backlog[channel][1:]
    utc_time = datetime.utcnow().timestamp()
    history_obj = ChatHistory(sender=client.fullmask, mtags=client.mtags, svid=client.user.account, utc_time=utc_time, sendtype=sendtype, data=message)
    ChatHistory.add_to_buff(channel, history_obj)


def add_to_historybuf_privmsg(client, channel, message):
    if 'H' not in channel.modes:
        return
    add_to_historybuf(client, channel, message, sendtype="PRIVMSG")


def add_to_historybuf_notice(client, channel, message):
    if 'H' not in channel.modes:
        return
    add_to_historybuf(client, channel, message, sendtype="NOTICE")


def show_history_on_join(client, channel):
    if 'H' not in channel.modes or not client.has_capability("server-time"):
        return

    if client in ChatHistory.reply_time and int(time()) - ChatHistory.reply_time[client] < 600:
        return

    history_filter = HistoryFilter()
    history_filter.cmd = ChatHistory.LATEST
    history_filter.limit = 10
    results = get_chathistory(channel, history_filter)
    send_history(client, channel, results)


def send_history(client, channel, results: list) -> None:
    if not client.has_capability("server-time"):
        return
    ChatHistory.reply_time[client] = int(time())
    batch = None
    if client.has_capability("batch"):
        batch = Batch(started_by=IRCD.me)
        client.send([], f":{IRCD.me.name} BATCH +{batch.label} chathistory {channel.name}")
    if results:
        for history_obj in results:
            filtered_mtags = []
            if batch:
                batch_tag = MessageTag.find_tag("batch")(value=batch.label)
                filtered_mtags.append(batch_tag)
            for tag in MessageTag.filter_tags(history_obj.mtags, client):
                filtered_mtags.append(tag)
            data = f"{'@' + ';'.join([t.string for t in filtered_mtags]) + ' ' if filtered_mtags else ''}" \
                   f":{history_obj.sender} {history_obj.sendtype} {channel.name} :{history_obj.data}"
            client.send([], data)

    if batch:
        client.send([], f":{IRCD.me.name} BATCH -{batch.label}")


def get_chathistory(channel, history_filter: HistoryFilter) -> list:
    if channel not in ChatHistory.backlog:
        return []

    results = []
    match history_filter.cmd:
        case ChatHistory.BEFORE:
            if history_filter.timestamp_1:
                time_float = ChatHistory.timestr_to_timestamp(history_filter.timestamp_1)
                for history_obj in ChatHistory.backlog[channel]:
                    if history_obj.utc_time < time_float and len(results) < history_filter.limit:
                        results.append(history_obj)
            elif history_filter.msgid_1:
                for history_obj in ChatHistory.backlog[channel]:
                    if history_obj.msgid == history_filter.msgid_1:
                        break
                    if len(results) < history_filter.limit:
                        results.append(history_obj)

        case ChatHistory.AFTER:
            if history_filter.timestamp_1:
                time_float = ChatHistory.timestr_to_timestamp(history_filter.timestamp_1)
                for history_obj in ChatHistory.backlog[channel]:
                    if history_obj.utc_time > time_float and len(results) < history_filter.limit:
                        results.append(history_obj)
            elif history_filter.msgid_1:
                msgid_found = 0
                for history_obj in ChatHistory.backlog[channel]:
                    if history_obj.msgid == history_filter.msgid_1:
                        msgid_found = 1
                        continue
                    if msgid_found and len(results) < history_filter.limit:
                        results.append(history_obj)

        case ChatHistory.LATEST:
            if not history_filter.timestamp_1 and not history_filter.msgid_1:
                for history_obj in ChatHistory.backlog[channel]:
                    if len(results) < history_filter.limit:
                        results.append(history_obj)

            elif history_filter.timestamp_1:
                time_float = ChatHistory.timestr_to_timestamp(history_filter.timestamp_1)
                for history_obj in ChatHistory.backlog[channel]:
                    if history_obj.utc_time < time_float and len(results) < history_filter.limit:
                        results.append(history_obj)

            elif history_filter.msgid_1:
                msgid_found = 0
                for history_obj in ChatHistory.backlog[channel]:
                    if history_obj.msgid == history_filter.msgid_1:
                        msgid_found = 1
                        continue
                    if msgid_found and len(results) < history_filter.limit:
                        results.append(history_obj)

        case ChatHistory.BETWEEN:
            if history_filter.timestamp_1 and history_filter.timestamp_2:
                time1_float = ChatHistory.timestr_to_timestamp(history_filter.timestamp_1)
                time2_float = ChatHistory.timestr_to_timestamp(history_filter.timestamp_2)
                msg_found = 0
                for history_obj in ChatHistory.backlog[channel]:
                    if history_obj.utc_time > time1_float and not msg_found:
                        msg_found = 1
                        continue
                    if history_obj.utc_time >= time2_float or len(results) >= history_filter.limit:
                        break
                    if msg_found:
                        results.append(history_obj)
            elif history_filter.msgid_1 and history_filter.msgid_2:
                msg_found = 0
                for history_obj in ChatHistory.backlog[channel]:
                    if history_obj.msgid == history_filter.msgid_1 and not msg_found:
                        msg_found = 1
                        continue
                    if history_obj.msgid == history_filter.msgid_2 or len(results) >= history_filter.limit:
                        break
                    if msg_found:
                        results.append(history_obj)
    return results


def chmode_H_mode(client, channel, modebuf, parambuf):
    if 'H' in modebuf:
        if 'H' not in channel.modes:
            del ChatHistory.backlog[channel]
        else:
            ChatHistory.backlog[channel] = []


def cmd_history(client, recv):
    """
    Syntax: HISTORY <channel>
    If channel mode +H is set on the channel, it will retrieve the last 10 messages spoken.
    """
    if not (channel := IRCD.find_channel(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL)

    if not channel.find_member(client) and not client.has_permission("channel:see:history"):
        return client.sendnumeric(Numeric.ERR_NOTONCHANNEL)

    if not client.has_capability("server-time"):
        return

    client.local.flood_penalty += 10_000
    history_filter = HistoryFilter(cmd=ChatHistory.LATEST, limit=10)
    results = get_chathistory(channel, history_filter)
    send_history(client, channel, results)


def check_chathistory_conf():
    if not (block := IRCD.configuration.get_block("chathistory")):
        conf_error(f"Missing configuration block chathistory {{ }}", block)
        return

    max_unreg = block.get_single_value("max-lines-unregistered")
    if not max_unreg:
        return conf_error(f"chathistory::max-lines-unregistered missing")

    max_reg = block.get_single_value("max-lines-registered")
    if not max_unreg:
        return conf_error(f"chathistory::max-lines-registered missing")

    if not max_unreg.isdigit() or int(max_unreg) <= 0:
        return conf_error("chathistory::max-lines-unregistered missing must be a positive number")

    if not max_unreg.isdigit() or int(max_reg) <= 0:
        return conf_error("chathistory::max-lines-registered missing must be a positive number")

    max_reg, max_unreg = int(max_reg), int(max_unreg)
    if max_reg > 10000:
        max_reg = 10000

    if max_unreg > 10000:
        max_unreg = 10000

    ChatHistory.max_reg = max_reg
    ChatHistory.max_unreg = max_unreg


def post_load(module):
    check_chathistory_conf()


def check_expired_backlog():
    for channel in list(ChatHistory.backlog):
        if 'H' not in channel.modes:
            del ChatHistory.backlog[channel]
            continue

        param = channel.get_param('H')
        expire = int(param.split(':')[1])
        utc_time = int(datetime.utcnow().timestamp())
        for history_entry in list(ChatHistory.backlog[channel]):
            if utc_time - int(history_entry.utc_time) >= (expire * 60):
                ChatHistory.backlog[channel].remove(history_entry)


def init(module):
    Chmode_H = Channelmode()
    Chmode_H.flag = 'H'
    Chmode_H.param_help = "[maxlines:expire_in_minutes]"
    Chmode_H.desc = "Saves up to <maxlines> channel messages for <expire_in_minutes> minutes"
    Chmode_H.conv_param = history_conv_param
    Chmode_H.is_ok = history_validate_param
    Chmode_H.paramcount = 1
    Chmode_H.level = 3
    Channelmode.add(module, Chmode_H)
    Command.add(module, cmd_history, "HISTORY", 1)
    Hook.add(Hook.LOCAL_CHANMSG, add_to_historybuf_privmsg)
    Hook.add(Hook.LOCAL_CHANNOTICE, add_to_historybuf_notice)
    Hook.add(Hook.LOCAL_JOIN, show_history_on_join)
    Hook.add(Hook.CHANNEL_CREATE, create_history_channel_create)
    Hook.add(Hook.CHANNEL_DESTROY, clear_history_channel_destroy)
    Hook.add(Hook.LOCAL_CHANNEL_MODE, chmode_H_mode)
    Hook.add(Hook.REMOTE_CHANNEL_MODE, chmode_H_mode)
    Hook.add(Hook.LOOP, check_expired_backlog)
