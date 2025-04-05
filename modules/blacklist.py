"""
Support for blacklist checks. Configure in dnsbl.conf
"""

import socket
from time import time
import ipaddress
import asyncio

from dataclasses import dataclass, field

from handle.core import IRCD, Hook, Numeric, Snomask
from modules.m_tkl import Tkl
from handle.functions import reverse_ip, valid_expire
from handle.validate_conf import conf_error
from handle.logger import logging

logging.getLogger("asyncio").setLevel(logging.WARNING)


@dataclass
class Blacklist:
    cache = []
    process = []
    tasks = {}

    def __init__(self, name: str = '', ip: str = '', reason: str = '', set_time: int = 0, duration: int = 0):
        self.name = name
        self.ip = ip
        self.reason = reason
        self.set_time = set_time
        self.duration = duration

    @staticmethod
    def find(ip):
        return next((b for b in Blacklist.cache if b.ip == ip), 0)


@dataclass
class Dnsbl:
    table = []

    name: str = ''
    dns: str = ''
    action: str = ''
    reason: str = ''
    duration: int = 0
    reply: list = field(default_factory=list)

    def __post_init__(self):
        Dnsbl.table.append(self)

    def __repr__(self):
        return f"<Dnsbl '{self.dns}'>"


async def dnsbl_check_client(client, dnsbl):
    if Blacklist.find(client.ip):
        return

    lookup = f"{reverse_ip(client.ip)}.{dnsbl.dns}"
    reason = dnsbl.reason.replace("%ip", client.ip)

    try:
        result = await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, socket.gethostbyname, lookup), timeout=5)
        reply = result.split('.')[3]

        if dnsbl.reply and reply not in dnsbl.reply:
            return

        entry = Blacklist(name=dnsbl.name, ip=client.ip, reason=reason, set_time=int(time()), duration=int(dnsbl.duration))
        Blacklist.cache.append(entry)

        msg = f"*** DNSBL match for IP {client.ip} [nick: {client.name}]: {reason}"
        IRCD.log(client, level="info", rootevent="blacklist", event="BLACKLIST_HIT", message=msg)

        if dnsbl.action == "gzline":
            client.sendnumeric(Numeric.RPL_TEXT, reason)
            client.exit(reason)
            Tkl.add(
                client=IRCD.me, flag='Z', ident='*', host=client.ip, bantypes='', set_by=IRCD.me.name,
                expire=int(time()) + dnsbl.duration, set_time=int(time()), reason=reason
            )

        if client.ip in Blacklist.tasks:
            for task in [t for t in Blacklist.tasks[client.ip] if not t.done()]:
                task.cancel()

            del Blacklist.tasks[client.ip]

    except (asyncio.TimeoutError, asyncio.CancelledError, socket.gaierror):
        pass

    except Exception as ex:
        logging.exception(f"Exception during DNSBL check for {client.ip} on {dnsbl.dns}: {ex}")


async def blacklist_check(client):
    if IRCD.is_except_client("dnsbl", client) or not ipaddress.ip_address(client.ip).is_global:
        return

    if blacklist := Blacklist.find(client.ip):
        for c in [c for c in IRCD.get_clients(local=1) if c.ip == client.ip]:
            c.sendnumeric(Numeric.RPL_TEXT, blacklist.reason)
            c.exit(blacklist.reason)
        return Hook.DENY

    if client.ip not in Blacklist.process:
        Blacklist.process.append(client.ip)
        client.sendnumeric(Numeric.RPL_TEXT, "* Please wait while your connection is being checked against DNSBL.")
        IRCD.delay_client(client, 1, "blacklist")
        try:
            Blacklist.tasks[client.ip] = [asyncio.create_task(dnsbl_check_client(client, dnsbl)) for dnsbl in Dnsbl.table]
            await asyncio.gather(*Blacklist.tasks[client.ip], return_exceptions=True)
        finally:
            Blacklist.process.remove(client.ip)
            IRCD.remove_delay_client(client)


def blacklist_expire():
    for bl in [bl for bl in list(Blacklist.cache) if bl.duration and int(time() > bl.duration + bl.set_time)]:
        Blacklist.cache.remove(bl)


def start_blacklist_check(client):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(blacklist_check(client))
    except RuntimeError:
        # No running event loop, create a new one.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(blacklist_check(client))
        finally:
            loop.close()


def init(module):
    Hook.add(Hook.NEW_CONNECTION, start_blacklist_check, priority=999)
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
                conf_error(f"Block '{block.name}' is missing item '{item}'", block=block)

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
            Dnsbl(dns=dnsbl_dns, action=dnsbl_action, reason=dnsbl_reason, reply=dnsbl_reply, duration=dnsbl_duration)
