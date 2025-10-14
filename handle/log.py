from handle.core import IRCD, Command
from classes.data import Flag


class LogEntry:
    color_table = {"warn": '7', "error": '4', "info": '3'}

    def __init__(self, client, level, rootevent, event, message):
        self.client = client
        self.level = level
        self.rootevent = rootevent
        self.event = event
        self.message = message
        self.snomask = Log.event_to_snomask(rootevent, event)


class Log:
    event_map = {
        # rootevent, event (optional), snomask
        ("connect", "LOCAL_USER_CONNECT"): 'c',
        ("connect", "LOCAL_USER_QUIT"): 'c',
        ("connect", "REMOTE_USER_CONNECT"): 'C',
        ("connect", "REMOTE_USER_QUIT"): 'C',
        ("spamfilter", None): 'F',
        ("flood", None): 'f',
        ("tkl", None): 'G',
        ("oper", None): 'o',
        ("link", None): 'L',
        ("kill", None): 'k',
        ("sajoin", None): 'S',
        ("sapart", None): 'S',
        ("sanick", None): 'S',
        ("join", None): 'j',
        ("part", None): 'j',
        ("kick", None): 'j',
        ("nick", "LOCAL_NICK_CHANGE"): 'n',
        ("nick", "REMOTE_NICK_CHANGE"): 'N',
        ("blacklist", None): 'd',
    }

    @staticmethod
    def event_to_snomask(rootevent, event):
        return Log.event_map.get((rootevent, event), Log.event_map.get((rootevent, None), 's'))

    @staticmethod
    def log_to_remote(log_entry: LogEntry):
        if IRCD.me.creationtime:
            source = log_entry.client.id if log_entry.client.id else log_entry.client.name
            data = f":{source} SLOG {log_entry.level} {log_entry.rootevent} {log_entry.event} {log_entry.message}"
            IRCD.send_to_servers(log_entry.client, [], data)

    @staticmethod
    def log(client, level: str, rootevent: str, event: str, message: str, sync: int = 1):
        """
        client:     Client information for the log event
        """

        source = client if client.server else client.uplink
        log_entry = LogEntry(source, level, rootevent, event, message)

        level_colored = f"{LogEntry.color_table.get(level, '')}[{level}]" if level in LogEntry.color_table else f"[{level}]"
        # out_msg = f"14{rootevent}.{event} {level_colored} {message}"
        out_msg = f"{level_colored} ({rootevent}) {message}"

        if log_entry.snomask:
            IRCD.send_snomask(client, log_entry.snomask, out_msg, sendsno=0)

        if log_chan := IRCD.find_channel(IRCD.get_setting("logchan")):
            log_chan.broadcast(source, f":{source.name} PRIVMSG {log_chan.name} :{out_msg}")

        if sync:
            Log.log_to_remote(log_entry)

    @staticmethod
    def cmd_slog(client, recv):
        # :source SLOG <level> <rootevent> <event> :message
        # :001 SLOG warn link EVENT :This is a warning
        level, rootevent, event = recv[1:4]
        message = ' '.join(recv[4:]).removeprefix(':').strip()
        IRCD.log(client, level, rootevent, event, message)

    Command.add(None, cmd_slog, "SLOG", 4, Flag.CMD_SERVER)
