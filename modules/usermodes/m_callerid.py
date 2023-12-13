"""
provides usermodes +g and /accept command (callerid)
"""

import time

from handle.core import IRCD, Command, Usermode, MessageTag, Isupport, Numeric, Hook
from handle.logger import logging


class CallerIDData:
    buffer = {}
    accept_list = {}
    last_notify = {}

    @staticmethod
    def add_to_buf(client, entry):
        if client not in CallerIDData.buffer:
            CallerIDData.buffer[client] = []
        CallerIDData.buffer[client].append(entry)

    @staticmethod
    def add_to_accept(client, nickname):
        if client not in CallerIDData.accept_list:
            CallerIDData.accept_list[client] = []
        CallerIDData.accept_list[client].append(nickname)

    @staticmethod
    def remove_from_accept(client, nickname):
        if client not in CallerIDData.accept_list:
            CallerIDData.accept_list[client] = []
        if nickname in CallerIDData.accept_list[client]:
            CallerIDData.accept_list[client].remove(nickname)

    @staticmethod
    def get_acceptlist(client):
        if client not in CallerIDData.accept_list:
            CallerIDData.accept_list[client] = []
        return CallerIDData.accept_list[client]

    @staticmethod
    def send_notify(client, target):
        """
        client          Client user object
        target          Target user object
        """
        if target not in CallerIDData.last_notify[client]:
            CallerIDData.last_notify[client][target] = int(time.time())
            return 1
        send_notify = (int(time.time()) - CallerIDData.last_notify[client][target]) > 60
        if send_notify:
            CallerIDData.last_notify[client][target] = int(time.time())
        return send_notify

    @staticmethod
    def send_buffer(client, nickname):
        for entry in list([entry for entry in CallerIDData.buffer[client] if entry.sourcenick.lower() == nickname.lower()]):
            data = ''
            if entry.mtags:
                filtered_tags = MessageTag.filter_tags(mtags=entry.mtags, destination=client)
                data += '@' + ';'.join([t.string for t in filtered_tags]) + ' '
            data += f":{entry.source} {entry.sendtype} {client.name} :{entry.message}"
            client.send([], data)
            CallerIDData.buffer[client].remove(entry)
            if entry.target in CallerIDData.last_notify[client]:
                del CallerIDData.last_notify[client][entry.target]

    @staticmethod
    def cleanup(client):
        if client in CallerIDData.buffer:
            del CallerIDData.buffer[client]
        if client in CallerIDData.last_notify:
            del CallerIDData.last_notify[client]
        if client in CallerIDData.accept_list:
            del CallerIDData.accept_list[client]

        for c in CallerIDData.last_notify:
            if client in list(CallerIDData.last_notify[c]):
                del CallerIDData.last_notify[c][client]

    @staticmethod
    def new_client(client):
        if client not in CallerIDData.buffer:
            CallerIDData.buffer[client] = []
        if client not in CallerIDData.accept_list:
            CallerIDData.accept_list[client] = []
        if client not in CallerIDData.last_notify:
            CallerIDData.last_notify[client] = {}


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
    """
    If the sender has usermodes +o (IRCop) or +S (service), do not deny.
    """
    if 'g' in target.user.modes and (not client.has_modes_any("oS") and not client.is_service and not client.ulined):
        if client.name.lower() not in [x.lower() for x in CallerIDData.get_acceptlist(target)]:
            if client.local:
                client.sendnumeric(Numeric.RPL_TARGUMODEG, target.name)
                client.sendnumeric(Numeric.RPL_TARGNOTIFY, target.name)
            if target.local:
                CallerIDEntry(source=client, target=target, message=msg, sendtype=sendtype)
                if CallerIDData.send_notify(client, target):
                    target.sendnumeric(Numeric.RPL_UMODEGMSG, client.name, f"{client.user.username}@{client.user.cloakhost}")
                return Hook.DENY
    return Hook.CONTINUE


def cmd_accept(client, recv):
    """Manipulate caller-ID list.
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

    for entry in recv[1].split(','):
        continue_loop = 0
        action = ''
        nickname = entry
        if entry[0] == '-':
            action = '-'
            nickname = entry[1:]
        for c in entry.lower():
            if c.lower() not in IRCD.NICKCHARS or nickname[0].isdigit() and client.local:
                continue_loop = 1
                break
        if continue_loop:
            continue

        accept_lower = [x.lower() for x in CallerIDData.get_acceptlist(client)]
        if action != '-':
            if nickname.lower() in accept_lower:
                client.sendnumeric(Numeric.ERR_ACCEPTEXIST, nickname)
                continue
        if action == '-':
            if nickname.lower() not in accept_lower:
                client.sendnumeric(Numeric.ERR_ACCEPTNOT, nickname)
                continue
            CallerIDData.remove_from_accept(client, nickname)
            continue
        CallerIDData.add_to_accept(client, nickname)
        CallerIDData.send_buffer(client, nickname)

    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, mtags=[], data=data)


def callerid_eos(remote_server):
    for client in CallerIDData.accept_list:
        if data := [a for a in CallerIDData.get_acceptlist(client)]:
            remote_server._send(f":{client.id} ACCEPT {','.join(data)}")


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
