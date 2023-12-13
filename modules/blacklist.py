import logging

from handle.core import IRCD, Hook, Numeric, Snomask, Tkl
from handle.functions import reverse_ip, valid_expire
from handle.validate_conf import conf_error
import socket
from time import time
import ipaddress


class Blacklist:
    cache = []
    process = []
    lookups = {}

    ip: str = ''
    reason: str = ''

    @staticmethod
    def find(ip):
        return next((b for b in Blacklist.cache if b.ip == ip), 0)

    @staticmethod
    def end_process(client, dnsbl):
        if client not in Blacklist.lookups:
            """ Removed early by QUIT hook """
            return
        Blacklist.lookups[client].remove(dnsbl)
        if not Blacklist.lookups[client]:
            if client.ip in Blacklist.process:
                Blacklist.process.remove(client.ip)
            IRCD.remove_delay_client(client, "blacklist")


class Dnsbl:
    table = []

    def __init__(self, dns, action, reason):
        self.dns = dns
        self.action = action
        self.duration = 0
        self.reason = reason
        self.reply = []
        Dnsbl.table.append(self)

    def __repr__(self):
        return f"<Dnsbl '{self.dns}'>"


def dnsbl_check_client(client, dnsbl):
    lookup = reverse_ip(client.ip) + '.' + dnsbl.dns
    reason = dnsbl.reason.replace("%ip", client.ip)
    try:
        result = socket.gethostbyname(lookup)
        Blacklist.end_process(client, dnsbl)
        reply = result.split('.')[3]
        if dnsbl.reply and reply not in dnsbl.reply:
            return
        if not Blacklist.find(client.ip):
            entry = Blacklist()
            entry.name = dnsbl.name
            entry.ip = client.ip
            entry.reason = reason
            entry.set_time = int(time())
            entry.duration = int(dnsbl.duration)
            Blacklist.cache.append(entry)
            msg = f"*** DNSBL match for IP {client.ip} [nick: {client.name}]: {reason}"
            IRCD.send_snomask(client, 'd', msg)

        if dnsbl.action == "gzline":
            client.sendnumeric(Numeric.RPL_TEXT, reason)
            client.exit(reason)
            Tkl.add(client=IRCD.me,
                    flag="Z",
                    ident="*",
                    host=client.ip,
                    bantypes='*',  # Not applicable, used for /eline.
                    set_by=IRCD.me.name,
                    expire=int(time()) + dnsbl.duration,
                    set_time=int(time()),
                    reason=reason)

    except socket.gaierror:  # [Errno -2] Name or service not known -> no match.
        Blacklist.end_process(client, dnsbl)
    except Exception as ex:
        logging.exception(ex)
        Blacklist.end_process(client, dnsbl)


def blacklist_check(client):
    if not client.user:
        return
    if IRCD.is_except_client("dnsbl", client):
        return
    if not ipaddress.ip_address(client.ip).is_global:
        return

    if blacklist := Blacklist.find(client.ip):
        for c in [c for c in IRCD.local_users() if c.ip == client.ip]:
            c.sendnumeric(Numeric.RPL_TEXT, blacklist.reason)
            c.exit(blacklist.reason)
        return Hook.DENY

    if client not in Blacklist.lookups:
        Blacklist.lookups[client] = []

    if client.ip not in Blacklist.process:
        client.sendnumeric(Numeric.RPL_TEXT, "* Please wait while your connection is being checked against DNSBL.")
        IRCD.delay_client(client, 1, "blacklist")
        Blacklist.process.append(client.ip)
        for dnsbl in Dnsbl.table:
            Blacklist.lookups[client].append(dnsbl)
            IRCD.run_parallel_function(target=dnsbl_check_client, args=(client, dnsbl))


def blacklist_expire():
    for bl in [bl for bl in list(Blacklist.cache) if bl.duration and int(time() >= bl.duration + bl.set_time)]:
        Blacklist.cache.remove(bl)


def blacklist_cleanup(client, *args):
    if client in Blacklist.lookups:
        del Blacklist.lookups[client]


def init(module):
    Hook.add(Hook.NEW_CONNECTION, blacklist_check, 999)
    Hook.add(Hook.LOCAL_QUIT, blacklist_cleanup)
    Hook.add(Hook.LOCAL_CONNECT, blacklist_cleanup)
    Hook.add(Hook.LOOP, blacklist_expire)
    Snomask.add(module, 'd', 1, "View DNSBL hits")


def post_load(module):
    if not (blocks := IRCD.configuration.get_blocks("dnsbl")):
        conf_error(f"Missing configuration block dnsbl {{ }}")
        return

    for block in blocks:
        if not block.value:
            conf_error(f"DNSBL is missing a name", block)
            return

        dnsbl_name = block.value

        required = ["dns", "action", "reason"]
        for item in required:
            if not block.get_path(dnsbl_name + ':' + item):
                conf_error(f"Block '{block.name}' is missing item '{item}'", filename=block.filename)

        dnsbl_dns = block.get_single_value("dns")
        if '.' not in dnsbl_dns:
            conf_error(f"DNS {dnsbl_dns} is invalid. Please use a valid hostname.")
            return

        dnsbl_reason = block.get_single_value("reason")

        dnsbl_duration = 0
        dnsbl_action = block.get_single_value("action")
        # If the action is 'gzline', also check for required duration.
        if dnsbl_action == "gzline":
            if not (dnsbl_duration := block.get_single_value("duration")):
                dnsbl_duration = "1d"
            if not (dnsbl_duration := valid_expire(dnsbl_duration)):
                dnsbl_duration = valid_expire("1d")

        dnsbl_reply = []
        if reply_items := block.get_items("reply"):
            for entry in reply_items:
                reply_value = entry.path[2]
                if not reply_value.isdigit():
                    conf_error(f"Reply value must be a digit. Invalid: {reply_value}", item=entry)
                    continue
                dnsbl_reply.append(reply_value)

        if dnsbl_dns and dnsbl_action and dnsbl_duration:
            dns = Dnsbl(dns=dnsbl_dns, action=dnsbl_action, reason=dnsbl_reason)
            dns.reply = dnsbl_reply
            dns.duration = dnsbl_duration
            dns.name = dnsbl_name
