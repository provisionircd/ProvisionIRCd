from handle.core import IRCD, Command, Flag
from handle.logger import logging


def event_to_snomask(rootevent, event):
    match rootevent:
        case "connect" | "quit":
            match event:
                case "LOCAL_USER_CONNECT" | "LOCAL_USER_QUIT":
                    return "c"
                case "REMOTE_USER_CONNECT" | "REMOTE_USER_QUIT":
                    return "C"
        case "oper":
            return "o"

        case "link":
            return "L"

        case "tkl":
            return "G"

        case "kill":
            return "k"

        case "sajoin" | "sapart" | "sanick":
            return "S"

        case _:
            return "s"


class LogEntry:
    color_table = {"warn": "7", "error": "4", "info": "3"}

    def __init__(self, client, level, rootevent, event, message):
        self.client = client
        self.level = level
        self.rootevent = rootevent
        self.event = event
        self.message = message
        self.snomask = event_to_snomask(rootevent, event)


def log_to_remote(log_entry: LogEntry):
    if not IRCD.boottime:
        return
    source = log_entry.client.id if log_entry.client.id else log_entry.client.name
    data = f":{source} SLOG {log_entry.level} {log_entry.rootevent} {log_entry.event} {log_entry.message}"
    IRCD.send_to_servers(log_entry.client.direction, [], data)


def log(client, level: str, rootevent: str, event: str, message: str, sync: int = 1):
    """
    client:     Client information for the log event
    """

    source = client if client.server else client.uplink
    log_entry = LogEntry(source, level, rootevent, event, message)

    if level in LogEntry.color_table:
        level_colored = f"{LogEntry.color_table[level]}[{level}]"
    else:
        level_colored = f"[{level}]"

    # out_msg = f"14{rootevent}.{event} {level_colored} {message}"
    out_msg = f"{level_colored} ({rootevent}) {message}"

    if log_entry.snomask:
        for oper_client in [c for c in IRCD.local_users() if 'o' in c.user.modes]:
            if log_entry.snomask not in oper_client.user.snomask:
                continue
            data = f":{source.name} NOTICE {oper_client.name} :{out_msg}"
            oper_client.send([], data)

    if log_chan := IRCD.find_channel(IRCD.get_setting("logchan")):
        data = f":{source.name} PRIVMSG {log_chan.name} :{out_msg}"
        log_chan.broadcast(source, data)

    if sync:
        log_to_remote(log_entry)


IRCD.log = log


def cmd_slog(client, recv):
    # :source SLOG <level> <rootevent> <event> :message
    # :001 SLOG warn link EVENT :This is a warning
    level = recv[1]
    rootevent = recv[2]
    event = recv[3]
    message = ' '.join(recv[4:]).removeprefix(':')
    # logging.info(f"SLOG from {client.name}: {recv}")
    # data = f":{client.id} {' '.join(recv)}"
    # IRCD.send_to_servers(client, [], data)
    IRCD.log(client, level, rootevent, event, message)


Command.add(None, cmd_slog, "SLOG", 4, Flag.CMD_SERVER)
