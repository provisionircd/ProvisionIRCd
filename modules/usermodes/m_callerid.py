"""
provides usermodes +g and /accept command (callerid)
"""

import time

from handle.core import IRCD, Command, Usermode, Isupport, Numeric, Hook
from modules.ircv3.messagetags import MessageTag


class CallerIDData:
    buffer = {}
    accept_list = {}
    last_notify = {}

    @staticmethod
    def add_to_buf(client, entry):
        CallerIDData.buffer.setdefault(client, []).append(entry)

    @staticmethod
    def add_to_accept(client, nickname):
        CallerIDData.accept_list.setdefault(client, []).append(nickname)

    @staticmethod
    def remove_from_accept(client, nickname):
        if nickname in CallerIDData.accept_list.setdefault(client, []):
            CallerIDData.accept_list[client].remove(nickname)

    @staticmethod
    def get_acceptlist(client):
        return CallerIDData.accept_list.setdefault(client, [])

    @staticmethod
    def send_notify(client, target) -> int:
        """
        :client:          Client user object
        :target:          Target user object
        """
        current_time = int(time.time())
        last_notify_time = CallerIDData.last_notify[client].get(target, 0)
        send_notify = current_time - last_notify_time > 60

        if send_notify:
            CallerIDData.last_notify[client][target] = current_time

        return send_notify

    @staticmethod
    def send_buffer(client, nickname):

        def send_buffer(client, nickname):
            nickname_lower = nickname.lower()
            entries_to_remove = []
            for entry in CallerIDData.buffer[client]:
                if entry.sourcenick.lower() == nickname_lower:
                    tag_part = ''
                    if entry.mtags:
                        if filtered_tags := MessageTag.filter_tags(mtags=entry.mtags, destination=client):
                            tag_part = '@' + ';'.join(t.string for t in filtered_tags) + ' '
                    client.send([], f"{tag_part}:{entry.source} {entry.sendtype} {client.name} :{entry.message}")
                    entries_to_remove.append(entry)
                    if entry.target in CallerIDData.last_notify[client]:
                        del CallerIDData.last_notify[client][entry.target]

            for entry in entries_to_remove:
                CallerIDData.buffer[client].remove(entry)

    @staticmethod
    def cleanup(client):
        CallerIDData.buffer.pop(client, None)
        CallerIDData.accept_list.pop(client, None)
        CallerIDData.last_notify.pop(client, None)
        for other_client_notifs in CallerIDData.last_notify.values():
            other_client_notifs.pop(client, None)

    @staticmethod
    def new_client(client):
        CallerIDData.buffer.setdefault(client, [])
        CallerIDData.accept_list.setdefault(client, [])
        CallerIDData.last_notify.setdefault(client, {})


class CallerIDEntry:
    def __init__(self, source, target, message, sendtype):
        self.source = source.fullmask
        self.sourcenick = source.name
        self.target = target
        self.message = message
        self.mtags = source.mtags
        self.sendtype = sendtype
        CallerIDData.add_to_buf(target, self)


def callerid_can_send_to_user(client, target, msg, sendtype):
    """ If the sender has usermodes +o (IRCop) or +S (service), do not deny. """
    if 'g' not in target.user.modes or client.has_modes_any("oS") or client.is_service() or client.is_uline():
        return Hook.CONTINUE

    client_name_lower = client.name.lower()
    if any(client_name_lower == x.lower() for x in CallerIDData.get_acceptlist(target)):
        return Hook.CONTINUE

    if client.local:
        client.sendnumeric(Numeric.RPL_TARGUMODEG, target.name)
        client.sendnumeric(Numeric.RPL_TARGNOTIFY, target.name)

    if target.local:
        CallerIDEntry(source=client, target=target, message=msg, sendtype=sendtype)
        if CallerIDData.send_notify(client, target):
            target.sendnumeric(Numeric.RPL_UMODEGMSG, client.name, f"{client.user.username}@{client.user.host}")

    return Hook.DENY


def cmd_accept(client, recv):
    """Manipulate caller-ID list.
    This list determines who can private message you.
    -
    Example: ACCEPT CoolGuy420      (Adds to list)
-            ACCEPT -R00T_UK        (Removes from list)
    To view your current list:
             ACCEPT *
    """
    if recv[1] == '*':
        for nick in CallerIDData.get_acceptlist(client):
            client.sendnumeric(Numeric.RPL_ACCEPTLIST, nick)
        return client.sendnumeric(Numeric.RPL_ENDOFACCEPT)

    accept_list_lower = [x.lower() for x in CallerIDData.get_acceptlist(client)]

    for entry in recv[1].split(','):
        if entry.startswith('-'):
            action = '-'
            nickname = entry[1:]
        else:
            action = ''
            nickname = entry

        if client.local and (any(c.lower() not in IRCD.NICKCHARS for c in nickname) or (nickname and nickname[0].isdigit())):
            continue

        nickname_lower = nickname.lower()

        if action == '+':
            if nickname_lower in accept_list_lower:
                client.sendnumeric(Numeric.ERR_ACCEPTEXIST, nickname)
                continue
            CallerIDData.add_to_accept(client, nickname)
            CallerIDData.send_buffer(client, nickname)

        else:
            if nickname_lower not in accept_list_lower:
                client.sendnumeric(Numeric.ERR_ACCEPTNOT, nickname)
                continue
            CallerIDData.remove_from_accept(client, nickname)

    IRCD.send_to_servers(client, mtags=[], data=f":{client.id} {' '.join(recv)}")


def callerid_eos(remote_server):
    for client, accept_list in CallerIDData.accept_list.items():
        if accept_list:
            remote_server.send([], f":{client.id} ACCEPT {','.join(accept_list)}")


def callerid_quit(client, reason):
    CallerIDData.cleanup(client)


def callerid_connect(client):
    CallerIDData.new_client(client)


def init(module):
    Command.add(module, cmd_accept, "ACCEPT", 1)
    Usermode.add(module, "g", 1, 0, Usermode.allow_all, "Only users in your accept-list can message you")
    Hook.add(Hook.SERVER_SYNCED, callerid_eos)
    Hook.add(Hook.LOCAL_QUIT, callerid_quit)
    Hook.add(Hook.LOCAL_CONNECT, callerid_connect)
    Hook.add(Hook.REMOTE_CONNECT, callerid_connect)
    Hook.add(Hook.CAN_SEND_TO_USER, callerid_can_send_to_user)
    Isupport.add("CALLERID")
