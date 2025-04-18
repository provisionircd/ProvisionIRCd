"""
/oper command
"""

import re

from handle.core import IRCD, Command, Numeric, Flag, Client, Capability, Hook
from handle.logger import logging

try:
    # noinspection PyPackageRequirements
    import bcrypt
except ImportError:
    bcrypt = None


class OperData:
    clients = {}

    @staticmethod
    def save_original_class(client):
        if client not in OperData.clients:
            OperData.clients[client] = {}
        OperData.clients[client]["class"] = client.class_

    @staticmethod
    def get_original_class(client):
        if client not in OperData.clients or "class" not in OperData.clients[client]:
            return None
        return OperData.clients[client]["class"]


def oper_check_certfp(client):
    if client.user.oper:
        return
    if not (fp := client.get_md_value("certfp")):
        return
    for oper in [oper for oper in IRCD.configuration.opers if oper.mask.is_match(client)]:
        if fp in oper.mask.certfp:
            msg = f"TLS fingerprint match: IRC Operator status automatically activated. [block: {oper.name}, class: {oper.operclass.name}]"
            IRCD.server_notice(client, msg)
            do_oper_up(client, oper)
            break


def oper_check_account(client):
    if client.user.oper or client.user.account == '*':
        return
    for oper in [oper for oper in IRCD.configuration.opers if oper.mask.is_match(client)]:
        if client.user.account in oper.mask.account:
            msg = (f"Account match [{client.user.account}]: IRC Operator status automatically activated. "
                   f"[block: {oper.name}, class: {oper.operclass.name}]")
            IRCD.server_notice(client, msg)
            do_oper_up(client, oper)
            break


def restore_class(client):
    if original_class := OperData.get_original_class(client):
        client.set_class_obj(original_class)


def do_oper_up(client, oper):
    if client.user.oper or not client.local:
        return

    OperData.save_original_class(client)
    client.set_class_obj(IRCD.get_class_from_name(oper.connectclass))

    # Do not automatically set following modes: gqrzH
    modes = 'o' + (re.sub(r"[ogqrzH]", '', oper.modes) if oper.modes else '')
    client.user.opermodes = ''
    for m in modes:
        if IRCD.get_usermode_by_flag(m) and m not in client.user.opermodes:
            client.user.opermodes += m
    client.user.operlogin = oper.name
    client.user.operclass = oper.operclass
    client.user.oper = oper
    client.backbuffer = []

    if 's' in modes:
        for snomask in oper.snomasks:
            if IRCD.get_snomask(snomask) and snomask not in client.user.snomask:
                client.user.snomask += snomask

    if 'x' not in client.user.modes and 'x' not in client.user.opermodes:
        client.user.opermodes += 'x'
    client.add_user_modes(client.user.opermodes)
    client.local.flood_penalty = 0
    if oper.swhois.strip():
        client.add_swhois(line=oper.swhois[:128], tag="oper", remove_on_deoper=1)

    if 't' in client.user.modes and oper.operhost and '@' not in oper.operhost and '!' not in oper.operhost:
        operhost = oper.operhost.strip('.').strip()
        if operhost and client.set_host(host=operhost):
            IRCD.send_to_servers(client, [], f":{client.id} SETHOST :{client.user.host}")

    msg = (f"*** {client.name} ({client.user.username}@{client.user.realhost}) "
           f"[block: {client.user.operlogin}, operclass: {client.user.operclass.name}] is now an IRC Operator")
    IRCD.log(client, "info", "oper", "OPER_UP", msg)

    if client.user.snomask:
        client.sendnumeric(Numeric.RPL_SNOMASK, client.user.snomask)
    client.sendnumeric(Numeric.RPL_YOUREOPER)

    client.add_md("operlogin", client.user.operlogin)
    client.add_md("operclass", client.user.operclass.name)

    IRCD.new_message(client)
    if oper_channel := IRCD.get_setting("oper-auto-join"):
        if not (oper_channel_obj := IRCD.find_channel(oper_channel)):
            oper_channel_obj = IRCD.create_channel(client, oper_channel)
        oper_channel_obj.do_join(client.mtags, client)
        if oper_channel_obj.topic_time != 0:
            Command.do(client, "TOPIC", oper_channel_obj.name)
        Command.do(client, "NAMES", oper_channel_obj.name)

    data = f":{client.name} UMODE +o"
    IRCD.send_to_local_common_chans(client, [], "oper-notify", data)


def oper_fail(client, opername, reason):
    client.local.flood_penalty += 350_000
    client.sendnumeric(Numeric.ERR_NOOPERHOST)
    IRCD.log(client, "warn", "oper", "OPER_FAILED", f"Failed oper attempt by {client.name}"
                                                    f"[{opername}] ({client.user.username}@{client.user.realhost}): {reason}")


def cmd_oper(client, recv):
    if client.user.oper:
        return IRCD.server_notice(client, f"You are already an IRC operator."
                                          f"To re-oper, first remove your current IRC operator status with: /mode {client.name} -o")
    if not (oper := IRCD.configuration.get_oper(recv[1])):
        oper_fail(client, recv[1], "username not found")
        return

    if oper.password and len(recv) > 2:
        if oper.password.startswith("$2b$") and len(oper.password) > 58 and bcrypt is not None:
            # noinspection PyUnresolvedReferences
            if not bcrypt.checkpw(recv[2].encode("utf-8"), oper.password.encode("utf-8")):
                oper_fail(client, recv[1], "incorrect password")
                return
        elif recv[2] != oper.password:
            oper_fail(client, recv[1], "incorrect password")
            return

    for m in oper.requiredmodes:
        if m not in client.user.modes and m not in "+-":
            oper_fail(client, recv[1], "mode requirement not met")
            return

    if not oper.mask.is_match(client):
        oper_fail(client, recv[1], "mask does not match")
        return

    total_classes = [c for c in Client.table if c.user and c.local and c.class_ == oper.connectclass]
    if len(total_classes) >= int(IRCD.configuration.get_class(oper.connectclass).max):
        oper_fail(client, recv[1], "associated oper class has reached its maximum instances")
        return

    do_oper_up(client, oper)


def watch_deoper(client, target, oldmodes, newmodes):
    if 'o' in set(oldmodes).difference(set(newmodes)):
        """ Only show -o for oper-notify """
        data = f":{target.name} UMODE -o"
        IRCD.send_to_local_common_chans(client, [], client_cap="oper-notify", data=data)
        restore_class(target)
        target.user.operclass = None
        target.user.operlogin = None
        target.user.oper = None

        for swhois in list(target.user.swhois):
            if swhois.remove_on_deoper or swhois.tag == "oper":
                target.del_swhois(swhois.line)

        target.del_md("operlogin")


def oper_new_connection(client):
    if client.user.oper:
        return
    oper_check_certfp(client)
    oper_check_account(client)


def oper_join(client, channel):
    if 'o' in client.user.modes and client.user.operlogin:
        IRCD.send_to_local_common_chans(client, [], client_cap="oper-notify", data=f":{client.fullmask} UMODE +o")


def operdata_clean(client, reason):
    if client in OperData.clients:
        del OperData.clients[client]


def oper_services_synced(server):
    if not server.is_service():
        return
    for client in IRCD.get_clients(local=1, user=1):
        oper_check_account(client)


def init(module):
    Command.add(module, cmd_oper, "OPER", 1, Flag.CMD_USER)
    Capability.add("oper-notify")
    Hook.add(Hook.UMODE_CHANGE, watch_deoper)
    Hook.add(Hook.LOCAL_CONNECT, oper_new_connection)
    Hook.add(Hook.LOCAL_JOIN, oper_join)
    Hook.add(Hook.LOCAL_QUIT, operdata_clean)
    Hook.add(Hook.SERVER_SYNCED, oper_services_synced)
