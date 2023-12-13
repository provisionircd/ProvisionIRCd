from handle.core import IRCD, Command, Isupport, Capability, Numeric
from handle.logger import logging
from modules.chanmodes.m_history import HistoryFilter, get_chathistory, send_history, ChatHistory
from datetime import datetime


def parse_history_filter(token: str, param: str, history_filter: HistoryFilter, attribute_name: str) -> int:
    if len(param.split('=')) != 2:
        return 0
    filter_name, filter_value = param.split('=')
    if token == "timestamp" and filter_name == token:
        try:
            datetime.strptime(filter_value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            return 0
        setattr(history_filter, attribute_name, filter_value)
        return 1
    elif token == "msgid" and filter_name == token:
        setattr(history_filter, attribute_name, filter_value)
        return 1


def cmd_chathistory(client, recv):
    if not client.has_capability("draft/chathistory") or not client.has_capability("server-time") or not client.has_capability("message-tags"):
        return
    target = recv[2]
    if not (channel := IRCD.find_channel(target)):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, target)

    if channel.find_member(client) and not client.has_permission("channel:see:history"):
        return client.sendnumeric(Numeric.ERR_NOTONCHANNEL)

    cmd = recv[1].lower()
    match cmd:
        case "before" | "after":
            history_filter = HistoryFilter()
            history_filter.cmd = ChatHistory.BEFORE if cmd == "before" else ChatHistory.AFTER
            if not parse_history_filter("timestamp", recv[3], history_filter, "timestamp_1") and not parse_history_filter("msgid", recv[3], history_filter, "msgid_1"):
                data = f"FAIL CHATHISTORY INVALID_PARAMS {recv[3]} :Invalid parameter, must be timestamp=xxx or msgid=xxx"
                return client.send([], data)
            limit = recv[4]
            if not limit.isdigit():
                return IRCD.server_notice(client, "Limit must be a number.")
            history_filter.limit = int(limit)
            results = get_chathistory(channel, history_filter)
            send_history(client, channel, results)
            return

        case "between":
            if len(recv) < 6:
                data = f"FAIL CHATHISTORY INVALID_PARAMS {recv[1]} :Insufficient parameters"
                return client.send([], data)
            history_filter = HistoryFilter()
            history_filter.cmd = ChatHistory.BETWEEN
            if not parse_history_filter("timestamp", recv[3], history_filter, "timestamp_1") and not parse_history_filter("msgid", recv[3], history_filter, "msgid_1"):
                data = f"FAIL CHATHISTORY INVALID_PARAMS {recv[3]} :Invalid parameter, must be timestamp=xxx or msgid=xxx"
                return client.send([], data)

            if not parse_history_filter("timestamp", recv[4], history_filter, "timestamp_2") and not parse_history_filter("msgid", recv[4], history_filter, "msgid_2"):
                data = f"FAIL CHATHISTORY INVALID_PARAMS {recv[4]} :Invalid parameter, must be timestamp=xxx or msgid=xxx"
                return client.send([], data)
            limit = recv[5]
            if not limit.isdigit():
                return IRCD.server_notice(client, "Limit must be a number.")
            history_filter.limit = int(limit)
            results = get_chathistory(channel, history_filter)
            send_history(client, channel, results)

        case "latest":
            history_filter = HistoryFilter()
            history_filter.cmd = ChatHistory.LATEST
            limit = recv[4]
            if not limit.isdigit():
                return IRCD.server_notice(client, "Limit must be a number.")
            history_filter.limit = int(limit)
            if recv[3] == '*':
                results = get_chathistory(channel, history_filter)
                send_history(client, channel, results)
                return
            if not parse_history_filter("timestamp", recv[3], history_filter, "timestamp_1") and not parse_history_filter("msgid", recv[3], history_filter, "msgid_1"):
                data = f"FAIL CHATHISTORY INVALID_PARAMS {recv[3]} :Invalid parameter, must be timestamp=xxx or msgid=xxx"
                return client.send([], data)
            results = get_chathistory(channel, history_filter)
            send_history(client, channel, results)


def init(module):
    Command.add(module, cmd_chathistory, "CHATHISTORY", 3)
    Capability.add("draft/chathistory")
    Isupport.add("CHATHISTORY")
