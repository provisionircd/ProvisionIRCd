import binascii
import datetime
import gc
import hashlib
import importlib
import itertools
import json
import logging
import os
import re
import string
import threading
import time
import sys
import socket
import selectors
import inspect
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

from random import randrange
from sys import version
from threading import Event
from time import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import ClassVar, Optional, Dict
from collections.abc import Callable

from OpenSSL import SSL

from handle.logger import logging, IRCDLogger
from classes.data import Numeric, Flag, Hook, Isupport
from handle.functions import is_match

gc.enable()

Client: type["Client"]
Channel: type["Channel"]
Channelmode: type["Channelmode"]
Module: type["Module"]
Configuration: type["Configuration"]


@dataclass
class Command:
    table: ClassVar[list] = []

    command: str = ''
    module: "Module" = None
    func: Callable = None
    trigger: str = ''
    parameters: int = 0
    flags: tuple = ()

    @staticmethod
    def add(module, func: Callable, trigger: str, params: int = 0, *flags: Flag):
        if not flags:
            flags = Flag.CMD_USER,

        if not isinstance(trigger, str):
            logging.error(f"Error loading module {module}: trigger must be a string, not {type(trigger)}")
            return
        cmd = Command(module=module, func=func, trigger=trigger, parameters=params, flags=flags)
        Command.table.append(cmd)

    def cmd_flags_match(self, client) -> tuple:
        # flags_sum = sum(e.value for e in command.flags)
        """
        0 = UNKNOWN (not yet fully registered on the server, assumes that it is a user)
        1 = USER
        2 = SERVER
        3 = OPER
        """

        if Flag.CMD_UNKNOWN not in self.flags and not client == IRCD.me and not client.registered and client.local and not client.server:
            return Numeric.ERR_NOTREGISTERED,

        if Flag.CMD_OPER in self.flags and client.user and 'o' not in client.user.modes and client.local:
            return Numeric.ERR_NOPRIVILEGES,

        if Flag.CMD_SERVER in self.flags and Flag.CMD_USER not in self.flags and Flag.CMD_OPER not in self.flags and not client.server:
            return Numeric.ERR_SERVERONLY, self.trigger.upper()

        return 0,

    def check(self, client, recv) -> tuple:
        result, *args = self.cmd_flags_match(client)
        if result != 0:
            return result, *args

        """ Don't count the actual command as a param. """
        if (len(recv) - 1) < self.parameters:
            return Numeric.ERR_NEEDMOREPARAMS, self.trigger.upper()
        return 0,

    @staticmethod
    def find_command(client, trigger: str, *recv):
        if cmd := next((command for command in Command.table if command.trigger.lower() == trigger.lower()), None):
            return cmd

        for alias in [a for a in IRCD.configuration.aliases if a.name.lower() == trigger.lower()]:
            if alias.target[0] in IRCD.CHANPREFIXES:
                if not (target := IRCD.find_channel(alias.target)):
                    logging.debug(f"Alias target channel {alias.target} not found.")
                    continue
            else:
                if alias.type == "services":
                    if not IRCD.find_client(IRCD.get_setting("services")):
                        client.sendnumeric(Numeric.ERR_SERVICESDOWN)
                        return 1

                if not (target := IRCD.find_client(alias.target)):
                    logging.debug(f"Alias target user {alias.target} not found.")
                    return 1

                if alias.type == "services" and target.uplink.name.lower() != IRCD.get_setting("services").lower():
                    return 1

            if target_client := IRCD.find_client(alias.target):
                data = f":{client.name} PRIVMSG {target_client.name}@{IRCD.get_setting('services')} :{' '.join(recv[1:])}"
                IRCD.send_to_one_server(target_client.uplink, client.mtags, data)
                return 1
        return 0

    @staticmethod
    def do(client: "Client", *recv):
        try:
            trigger = recv[0]
            if cmd := Command.find_command(client, trigger):
                for result, callback in Hook.call(Hook.PRE_COMMAND, args=(client, recv)):
                    if result == Hook.DENY:
                        logging.debug(f"PRE_COMMAND denied by {callback}")
                        logging.debug(f"Recv: {recv}")
                        return
                client.last_command = recv
                cmd.func(client, recv=list(recv))
                if client.user:
                    client.del_flag(Flag.CLIENT_CMD_OVERRIDE)
                IRCD.run_hook(Hook.POST_COMMAND, client, trigger, recv)
                client.mtags.clear()
                client.recv_mtags.clear()
                client.flood_safe_off()
        except Exception as ex:
            logging.exception(ex)

    @staticmethod
    def require_authentication(func):
        def wrapper(client, recv):
            if client.is_local_user() and client.user.account == '*':
                return client.sendnumeric(Numeric.ERR_CANNOTDOCOMMAND, recv[0].upper(), "You are not authenticated")
            return func(client, recv)

        return wrapper

    @staticmethod
    def require_oper(func):
        def wrapper(client, recv):
            if client.is_local_user() and 'o' not in client.user.modes:
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
            return func(client, recv)

        return wrapper

    @staticmethod
    def paramcount(paramcount):
        def decorator(func):
            def wrapper(client, recv):
                if client.is_local_user() and (len(recv) - 1) < paramcount:
                    cmd = recv[0].upper()
                    return client.sendnumeric(Numeric.ERR_NEEDMOREPARAMS, cmd)
                return func(client, recv)

            return wrapper

        return decorator


@dataclass
class Usermode:
    table: ClassVar[list] = []

    flag: str = ''
    is_global: int = 1
    unset_on_deoper: int = 0
    can_set: Callable = None
    module: "Module" = None
    desc: str = ''

    @staticmethod
    def add(module, flag: str, is_global: int, unset_on_deoper: int, can_set: callable, desc: str):
        if exists := next((um for um in Usermode.table if um.flag == flag), 0):
            logging.error(f"[{module.name}] Attempting to add user mode '{flag}'"
                          f"but it has already been added before by {exists.module.name}")
            if not IRCD.rehashing:
                sys.exit()
            return
        umode = Usermode(module=module, flag=flag, is_global=is_global, unset_on_deoper=unset_on_deoper, can_set=can_set, desc=desc)
        Usermode.table.append(umode)
        Isupport.add("USERMODES", Usermode.umodes_sorted_str(), server_isupport=1)

    @staticmethod
    def add_generic(flag: str):
        Usermode.table.append(Usermode(module=None, flag=flag, can_set=Usermode.allow_none))
        logging.debug(f"Adding generic support for missing user mode: {flag}")

    @staticmethod
    def allow_all(client):
        return 1

    @staticmethod
    def allow_opers(client):
        if client == IRCD.me or not client.local or client.has_flag(Flag.CLIENT_CMD_OVERRIDE):
            return 1
        return 'o' in client.user.modes and client.has_permission("self:opermodes")

    @staticmethod
    def allow_none(client):
        if client == IRCD.me or not client.local or client.has_flag(Flag.CLIENT_CMD_OVERRIDE):
            return 1
        return 0

    @staticmethod
    def umodes_sorted_str():
        return ''.join(sorted([cmode.flag for cmode in Usermode.table]))

    def get_level_string(self):
        levels = {
            Usermode.allow_opers: "IRCops only",
            Usermode.allow_none: "Settable by servers"
        }
        return levels.get(self.can_set)


@dataclass
class Snomask:
    table: ClassVar[list] = []

    module: "Module" = None  # noqa: F821
    flag: str = ''
    is_global: int = 0
    desc: str = ''

    @staticmethod
    def add(module, flag: str, is_global: int = 0, desc=''):
        if next((s for s in Snomask.table if s.flag == flag), 0):
            logging.error(f"Attempting to add duplicate snomask: {flag}")
            if not IRCD.rehashing:
                sys.exit()
            return
        Snomask.table.append(Snomask(module=module, flag=flag, is_global=is_global, desc=desc))


@dataclass
class Swhois:
    priority: int = 0
    line: str = ''
    tag: str = ''
    remove_on_deoper: int = 0

    @staticmethod
    def add_to_client(client: "Client", line: str, tag: str, remove_on_deoper=0):
        if next((sw for sw in client.user.swhois if sw.line == line), 0):
            return
        swhois = Swhois(line=line, tag=tag, remove_on_deoper=remove_on_deoper)
        client.user.swhois.append(swhois)
        IRCD.send_to_servers(client, [], f":{IRCD.me.id} SWHOIS {client.id} + {tag} :{swhois.line}")

    @staticmethod
    def remove_from_client(client: "Client", line: str):
        if not (swhois := next((swhois for swhois in client.user.swhois if swhois.line == line), 0)):
            return
        client.user.swhois.remove(swhois)
        IRCD.send_to_servers(client, [], f":{IRCD.me.id} SWHOIS {client.id} - {swhois.tag} :{swhois.line}")


class IRCD:
    me: "Client" = None
    configuration: "Configuration" = None  # Final configuration class.
    hostinfo: str = ''
    conf_path: str = ''
    conf_file: str = ''
    modules_dir: str = ''
    isupport: ClassVar[list] = []
    throttle: ClassVar[dict[str, deque]] = defaultdict(lambda: deque(maxlen=100))
    hostcache: ClassVar[dict[str, tuple[int, str]]] = {}
    client_by_id: ClassVar[Dict[str, "Client"]] = {}
    client_by_name: ClassVar[Dict[str, "Client"]] = {}
    client_by_sock: ClassVar[Dict[socket, "Client"]] = {}
    channel_by_name: ClassVar[Dict[str, "Channel"]] = {}
    maxusers: int = 0
    maxgusers: int = 0
    local_user_count: int = 0
    global_user_count: int = 0
    local_client_count: int = 0
    channel_count: int = 0
    rehashing: int = 0
    rootdir: str = ''
    confdir: str = ''
    default_tls = {"ctx": None, "keyfile": None, "certfile": None}
    current_link_sync: "Client" = None

    # When we receive remote server data during a server sync,
    # we will wait until all servers are synced before processing it.
    process_after_eos: ClassVar[list] = []

    # When we try to send data while still syncing to it,
    # we will save it and send it after we receive their EOS.
    send_after_eos: ClassVar[dict] = {}
    delayed_connections: ClassVar[list] = []
    pending_close_clients: ClassVar[list] = []
    versionnumber: str = "3.0"
    version: str = f"ProvisionIRCd-{versionnumber}-beta"
    running: int = 0
    poller = None
    selector = selectors.DefaultSelector()
    last_activity: int = 0
    uid_iter = None
    websocketbridge = None
    executor = ThreadPoolExecutor()
    command_socket = None
    logger = IRCDLogger
    pid: int = 0
    NICKLEN: int = 0
    ascii_letters_digits = ''.join([string.ascii_lowercase,
                                    string.digits,
                                    # à - ÿ (includes ö, ä, ü, é, è, ñ)
                                    ''.join([chr(i) for i in range(0x00E0, 0x00FF)]),
                                    # α - ω
                                    ''.join([chr(i) for i in range(0x03B1, 0x03C9 + 1)])
                                    ])

    NICKCHARS = ascii_letters_digits + "`^-_[]{}|\\"
    CHANPREFIXES = "#+&"
    CHANCHARS = ascii_letters_digits + "`#$^*()-=_[]{}|;':\"<>"
    HOSTCHARS = "abcdefghijklmnopqrstuvwxyz0123456789.-"

    @staticmethod
    def boot(fork=1):
        IRCD.pid = os.getpid()
        IRCD.me.server = IRCD.me
        IRCD.me.direction = IRCD.me
        IRCD.me.uplink = IRCD.me
        IRCD.hostinfo = "Python " + version.split('\\n')[0].strip()
        Isupport.add("NETWORK", IRCD.me.info.replace(' ', '-'))

        if fork and os.name == "posix" and (pid := os.fork()):
            logging.info(f"PID [{pid}] forking to the background")
            IRCDLogger.fork()
            sys.exit()

        IRCD.running = 1
        IRCD.init_log()
        IRCD.run_hook(Hook.BOOT)
        from handle.sockets import handle_connections
        handle_connections()

    @staticmethod
    def shutdown():
        IRCD.running = 0
        sys.exit()

    @staticmethod
    def restart():
        IRCD.running = 0
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @staticmethod
    def log(client, level: str, rootevent: str, event: str, message: str, sync: int = 1):
        pass

    @staticmethod
    def get_setting(key):
        return IRCD.configuration.settings.get(key)

    @staticmethod
    def set_setting(key, value):
        IRCD.configuration.settings[key] = value

    @staticmethod
    def get_attribute_from_module(attribute, package=None, header=None):
        if header and (mod := IRCD.module_by_header_name(header)):
            return getattr(mod.module, attribute, None)

        if package:
            try:
                module = importlib.import_module(package.replace('/', '.'))
                return getattr(module, attribute, None)
            except ModuleNotFoundError:
                return

    @staticmethod
    def get_module_by_package(package):
        return next((m for m in IRCD.configuration.modules if m.name == package), None)

    @staticmethod
    def is_except_client(what: str, client: "Client") -> int:
        """
        :param what:        What to check for. Examples are: gline, shun, dnsbl.
                            If what == 'ban', it will collectively check for all the following:
                            kline, gline, zline, gzline, shun, spamfilter, dnsbl, throttle, require
        :type what:         str
        :param client:      Client
        """

        if not client.user or not client.local:
            return 1

        what = what.lower()
        if any((e.name == "ban" and what in e.types and e.mask.is_match(client)) or
               (e.name == what and e.mask.is_match(client)) for e in IRCD.configuration.excepts):
            return 1

        if not (Tkl := IRCD.get_attribute_from_module("Tkl", "modules.m_tkl")):
            return 0

        # Check /eline matches
        for tkl in [tkl for tkl in Tkl.table if tkl.type == 'E']:
            if what == "ban" and not any(t in "kGzZsFd" for t in tkl.bantypes):
                continue

            if (tkl_what := Tkl.get_flag_of_what(what)) and tkl_what.flag not in tkl.bantypes:
                continue

            if (what == "dnsbl" and 'd' not in tkl.bantypes) or (what == "spamfilter" and 'F' not in tkl.bantypes):
                continue

            if tkl.ident == "~certfp:" and ((fp := client.get_md_value("certfp")) and fp == tkl.host):
                return 1

            if tkl.ident == "~account:" and client.user.account != '*' and (tkl.host == '*' or is_match(tkl.host, client.user.account)):
                return 1

            ident = client.user.username or '*'
            if any(is_match(tkl.mask, mask) for mask in [f"{ident}@{client.user.realhost}", f"{ident}@{client.ip}", client.ip]):
                return 1
        return 0

    @staticmethod
    def is_ban_client(what, client, data=None):
        """
        what:       user, nick
        As defined in bans.conf
        """

        if IRCD.is_except_client("ban", client):
            return 0

        for ban in [ban for ban in IRCD.configuration.bans if ban.type == what]:
            if what == "nick" and data and any(is_match(mask.lower(), data.lower()) for mask in ban.mask.mask):
                return ban
            elif ban.mask.is_match(client):
                return ban
        return 0

    @staticmethod
    def write_data_file(json_dict: dict, filename: str) -> None:
        os.makedirs("data", exist_ok=True)
        with open(f"data/{filename}", "w+") as f:
            f.write(json.dumps(json_dict, indent=4))

    @staticmethod
    def read_data_file(filename: str) -> dict:
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(f"data/{filename}"):
            return {}
        try:
            with open(f"data/{filename}") as f:
                return json.load(f)
        except json.decoder.JSONDecodeError as ex:
            logging.exception(ex)
            return {}

    @staticmethod
    def write_to_file(file: str, text: str) -> int:
        try:
            os.makedirs(os.path.dirname(file) or '.', exist_ok=True)
            with open(file, 'a') as f:
                f.write(f"{' '.join(text) if isinstance(text, list) else text}\n")
            return 1
        except Exception as ex:
            logging.exception(ex)
            return 0

    @staticmethod
    def read_from_file(file: str) -> str:
        return open(file, 'r').read() if os.path.exists(file) else ''

    @staticmethod
    def delay_client(client: "Client", delay: int | float, label: str):
        """
        Delay a client for maximum <delay> seconds.
        If the process that called this method ends earlier,
        the delay will be removed before <delay>.
        """

        if not client.local or not client.user:
            return

        expire = time() + delay
        if (d := next((d for d in IRCD.delayed_connections if d[0] == client and d[2] == label), 0)) and d[1] > expire:
            # Client is already being delayed with a longer delay than given, keeping that one instead
            return
        IRCD.delayed_connections.append((client, expire, label))

    @staticmethod
    def remove_delay_client(client, label=None):
        if not client.local or not client.user:
            return

        IRCD.delayed_connections = [entry for entry in IRCD.delayed_connections
                                    if not (entry[0] == client and (not label or entry[2] == label))]
        if not any(d[0] == client for d in IRCD.delayed_connections) and client.handshake_finished():
            client.register_user()

    @staticmethod
    def is_valid_channelname(name: str) -> int:
        return name[0] in IRCD.CHANPREFIXES and all(char.lower() in IRCD.CHANCHARS for char in name[1:])

    @staticmethod
    def strip_format(string: str) -> str:
        """ Strips all colors, bold, underlines, italics etc. from a string, and then returns it. """
        regex = re.compile(r"\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)
        stripped = regex.sub('', string).strip()
        return stripped

    @staticmethod
    def clean_string(string: str, charset: str, maxlen: int) -> str:
        cleaned = string[:maxlen].strip()
        out = ''.join(c for c in cleaned if c.lower() in charset)
        return out

    @staticmethod
    def parse_remote_mtags(self, remote_mtags) -> list:
        if not (MessageTag := IRCD.get_attribute_from_module("MessageTag", header="ircv3/messagetags", package="modules.ircv3.messagetags")):
            return []

        mtags = []
        for tag in remote_mtags:
            name, value = tag.split('=') if '=' in tag else (tag, None)
            if not (tag_class := MessageTag.find_tag(name)):
                continue

            new_tag = tag_class(value=value)
            if self.is_local_user() and not tag_class.is_client_tag():
                continue

            if tag_class.local and not self.is_local_user():
                continue

            if new_tag.is_client_tag() and not new_tag.can_send(self):
                continue

            if not new_tag.value_is_ok(value) or (tag_class.value_required and not value):
                continue

            # Keep original name, such as originating server name in oper-tag.
            new_tag.name = name
            mtags.append(new_tag)

        return mtags

    @staticmethod
    def do_delayed_process():
        """ Process all deferred server messages after link sync completes. """
        deferred_servers = list(IRCD.process_after_eos)
        if deferred_servers and any(IRCD.get_clients(server=1, registered=0)):
            logging.warning(f"Received do_delayed_process() but some servers are still not done syncing.")
            return

        IRCD.process_after_eos.clear()

        for server in deferred_servers:
            logging.debug(f"Processing deferred buffer for: {server.name}")
            server.handle_recv()

    @staticmethod
    def client_match_mask(client, mask):
        ident = client.user.username if client.user else '*'

        if is_match(mask, f"{client.name}!{ident}@{client.user.host}"):
            return 1
        if is_match(mask, f"{client.name}!{ident}@{client.user.cloakhost}"):
            return 1
        if is_match(mask, f"{client.name}!{ident}@{client.user.realhost}"):
            return 1
        if is_match(mask, f"{client.name}!{ident}@{client.ip}"):
            return 1
        if is_match(mask, f"{client.name}!{ident}@{client.user.vhost}"):
            return 1

        return 0

    @staticmethod
    def run_parallel_function(target, args=(), kwargs=None, delay=0.0):
        """
        Run a threaded function once with optional delay.
        Does not return anything.
        """

        kwargs = kwargs or {}

        def delayed_target():
            if delay > 0:
                Event().wait(delay)
            target(*args, **kwargs)

        IRCD.executor.submit(delayed_target)

    @staticmethod
    def kill_parallel_tasks():
        if hasattr(IRCD.executor, "_work_items"):
            for future_id in list(IRCD.executor._work_items.keys()):  # noqa
                IRCD.executor._work_items[future_id].future.cancel()  # noqa
        IRCD.executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def initialise_uid_generator():
        while 1:
            yield from (IRCD.me.id + ''.join(i) for i in itertools.product(string.ascii_uppercase, repeat=6))

    @staticmethod
    def get_next_uid():
        IRCD.uid_iter = IRCD.uid_iter or IRCD.initialise_uid_generator()
        while (uid := next(IRCD.uid_iter)) and IRCD.find_client(uid):
            pass
        return uid

    @staticmethod
    def get_random_interval(start: int = 30, max: int = 86400) -> int:  # noqa
        interval = start
        if hasattr(IRCD.me, "id"):
            interval += sum(int(char) for char in IRCD.me.id if char.isdigit())
        return interval + randrange(max)

    @staticmethod
    def get_cloak(client, host=None, key=None):
        """
        host = received hostname, depending on resolve settings.
        Can either be IP or realhost.
        """

        host = host or client.user.realhost
        ip = host if host else client.ip

        if "static" in host or ".ip-" in host:
            host = ip

        cloak_key = key or IRCD.get_setting("cloak-key")
        key_bytes = bytes(f"{host}{cloak_key}", "utf-8")
        hex_dig = hashlib.sha512(key_bytes).hexdigest()
        cloak1 = hex(binascii.crc32(bytes(hex_dig[0:32], "utf-8")) % (1 << 32))[2:]
        cloak2 = hex(binascii.crc32(bytes(hex_dig[32:64], "utf-8")) % (1 << 32))[2:]

        if host.replace('.', '').isdigit():
            cloak3 = hex(binascii.crc32(bytes(hex_dig[64:96], "utf-8")) % (1 << 32))[2:]
            return f"{cloak1}.{cloak2}.{cloak3}.IP"

        c = next((i + 1 for i, part in enumerate(host.split('.')) if part.replace('-', '').isalpha()), 1)
        c = max(c, 2)
        host = '.'.join(host.split('.')[c - 1:])
        prefix = f"{IRCD.get_setting('cloak-prefix')}-" if IRCD.get_setting("cloak-prefix") else ''
        return f"{prefix}{cloak1}.{cloak2}.{host}".strip('.')

    @staticmethod
    def get_member_prefix_str_sorted(reverse=True):
        prefix_sorted = sorted([m for m in IRCD.channel_modes() if m.prefix and m.rank and m.is_member_type()],
                               key=lambda c: c.rank, reverse=reverse)
        return ''.join([m.prefix for m in prefix_sorted])

    @staticmethod
    def get_time_string():
        utc_now = datetime.now(timezone.utc)
        return f"{utc_now:%Y-%m-%dT%H:%M:%S}.{utc_now.microsecond // 1000:03d}Z"

    @staticmethod
    def get_class_from_name(name: str):
        return next((cls for cls in IRCD.configuration.connectclass if cls.name == name), None)

    @staticmethod
    def get_link(name: str):
        return next((link for link in IRCD.configuration.links if link.name.lower() == name.lower()), None)

    @staticmethod
    def module_by_header_name(name: str):
        return next((m for m in IRCD.configuration.modules if m.header.get("name") == name), None)

    @staticmethod
    def find_command(trigger: str) -> Command:
        return next((c for c in Command.table if c.trigger.lower() == trigger.lower()), None)

    @staticmethod
    def get_usermode_by_flag(flag: str):
        return next((umode for umode in Usermode.table if umode.flag == flag), 0)

    @staticmethod
    def get_parammodes_str() -> str:
        return ''.join([cmode.flag for cmode in IRCD.channel_modes() if cmode.paramcount])

    @staticmethod
    def get_list_modes_str() -> str:
        return ''.join([cmode.flag for cmode in IRCD.channel_modes() if cmode.is_listmode_type()])

    @staticmethod
    def get_member_modes_str() -> str:
        return ''.join([cmode.flag for cmode in IRCD.channel_modes() if cmode.is_member_type()])

    @staticmethod
    def get_umodes_str():
        return ''.join(sorted(m.flag for m in Usermode.table))

    @staticmethod
    def get_chmodes_str():
        return ''.join(sorted(m.flag for m in IRCD.channel_modes()))

    @staticmethod
    def get_chmodes_str_categorized():
        categories = [[], [], [], []]
        for mode in [m for m in IRCD.channel_modes() if not m.is_member_type()]:
            if mode.is_listmode_type():
                categories[0].append(mode.flag)
            elif mode.unset_with_param:
                categories[1].append(mode.flag)
            elif mode.paramcount and not mode.unset_with_param:
                categories[2].append(mode.flag)
            else:
                categories[3].append(mode.flag)

        return ','.join(''.join(category) for category in categories)

    @staticmethod
    def channel_modes():
        return Channel.modes_table

    @staticmethod
    def get_channelmode_by_flag(flag: str):
        return next((m for m in IRCD.channel_modes() if m.flag == flag), 0)

    @staticmethod
    def get_clients(local=None, registered=None, user=None, server=None, usermodes: str = '', cap: str = ''):
        """
        Unified method to get filtered clients with flexible parameter combinations

        Parameters:
        - local: None (any), 1 (local only), 0 (remote only)
        - registered: None (any), 1 (registered only), 0 (unregistered only)
        - user: None (any), 1 (users only), 0 (non-users only)
        - server: None (any), 1 (servers only), 0 (non-servers only)
        - usermodes: Filter users with all these modes (empty string = no filter)
        - cap: Filter clients with this capability (empty string = no filter)

        Examples:
        - get_clients(local=1, user=1): All local users
        - get_clients(server=1, registered=0): All unregistered servers
        - get_clients(local=0, server=1): All remote servers
        """

        clients = Client.table

        if local is not None:
            clients = (c for c in clients if bool(c.local) == bool(local))

        if registered is not None:
            clients = (c for c in clients if bool(c.registered) == bool(registered))

        if user is not None:
            clients = (c for c in clients if bool(c.user) == bool(user))

        if server is not None:
            clients = (c for c in clients if bool(c.server) == bool(server))

        if usermodes:
            clients = (c for c in clients if c.user and all(mode in c.user.modes for mode in usermodes))

        if cap:
            clients = (c for c in clients if c.has_capability(cap))

        return clients

    @staticmethod
    def get_channels() -> list:
        """ Returns complete Channel.table list holding Channel objects. """
        return Channel.table

    @staticmethod
    def find_channel(name: str) -> Optional["Channel"]:
        """
        Finds a Channel object based on name, and then returns it.
        If no match can be found, None will be returned.
        """

        if not name:
            return

        return IRCD.channel_by_name.get(name.lower())

    @staticmethod
    def common_channels(p1, p2):
        """ Return common channels between p1 and p2 """
        return [c for c in IRCD.get_channels() if c.find_member(p1) and c.find_member(p2)]

    @staticmethod
    def create_channel(client, name: str):
        current_time = int(time())
        channel = Channel(name=name, creationtime=current_time, local_creationtime=current_time)
        channel.init_lists()
        Channel.table.append(channel)
        IRCD.channel_count += 1
        IRCD.channel_by_name[name.lower()] = channel
        IRCD.run_hook(Hook.CHANNEL_CREATE, client, channel)
        return channel

    @staticmethod
    def destroy_channel(client, channel):
        Channel.table.remove(channel)
        IRCD.channel_by_name.pop(channel.name.lower(), None)
        IRCD.channel_count -= 1
        IRCD.run_hook(Hook.CHANNEL_DESTROY, client, channel)

    @staticmethod
    def find_client(find: str | socket.socket, user=0, server=0):
        """ Find a client based on ID/name """

        if not find:
            return

        if isinstance(find, str):
            find = find.removeprefix(':').lower()

        if IRCD.running and find in {IRCD.me.name.lower(), IRCD.me.id.lower()} and not user:
            return IRCD.me

        if target := IRCD.client_by_id.get(find) or IRCD.client_by_name.get(find) or IRCD.client_by_sock.get(find):
            if user and not target.user:
                return
            if server and not target.server:
                return
            return target

    @staticmethod
    def find_server_match(find: str) -> list:
        """ Support for wildcards. """
        if not find:
            return []

        pattern = find.removeprefix(':').lower()
        servers = [IRCD.me] + [c for c in Client.table if c.server and c.id]
        return [s for s in servers if is_match(pattern, s.name.lower()) or is_match(pattern, s.id.lower())]

    @staticmethod
    def run_hook(hook, *args) -> None:
        for _, _ in Hook.call(hook, args=args):
            pass

    @staticmethod
    def init_log() -> None:
        from handle.log import Log
        IRCD.log = Log.log

    @staticmethod
    def new_message(client) -> None:
        if not client.local and client.recv_mtags:
            """ Remote clients mtags are already stored -- don't overwrite """
            return

        client.mtags = client.recv_mtags
        IRCD.run_hook(Hook.NEW_MESSAGE, client)
        # Filter duplicate tags from self.sender.mtags, keeping only first.
        seen = set()
        client.mtags = [tag for tag in client.mtags if tag.name not in seen and not seen.add(tag.name)]

    @staticmethod
    def send_to_one_server(client: "Client", mtags: list, data: str) -> None:
        """
        Send a message to a single server in a straight line
        skipping irrelevant servers.
        """

        destination = client if client.local else client.direction
        destination.send(mtags, data)

    @staticmethod
    def send_to_servers(client: "Client", mtags: list, data: str) -> None:
        """
        :param client:      The server from where this message is coming from.
        :param mtags:       Message tags.
        :param data:        Data to be sent.
        """

        for to_client in [c for c in Client.table if c.server and c.local]:
            if (client and client != IRCD.me and to_client == client.direction) or to_client.has_flag(Flag.CLIENT_EXIT):
                continue

            if IRCD.current_link_sync == to_client and to_client.server.authed:
                """ Destination server is not done syncing. """
                logging.warning(f"[send_to_servers()] Trying to sync data to server {to_client.name} but we're still syncing to it.")
                # Sending after we receive their EOS.
                logging.warning(f"This data is: {data.rstrip()}")
                if to_client not in IRCD.send_after_eos:
                    IRCD.send_after_eos[to_client] = []

                IRCD.send_after_eos[to_client].append((mtags, data))
                return

            to_client.send(mtags, data)

    @staticmethod
    def send_to_local_common_chans(client, mtags, client_cap=None, data: str = '') -> None:
        """
        Sends a message to local users sharing a common channel with the sender.

        Checks various conditions like channel membership, visibility, 'seen' status,
        and client capabilities before sending. Sends only once per recipient,
        based on the first common channel found that meets all criteria.

        Args:
            client: The client sending the message.
            mtags: Message tags list to send.
            client_cap (optional): A capability required by the recipient. Defaults to None.
            data (required): The message string to be sent.
        """
        if not data:
            return
        sent_clients = set()
        target_clients = (c for c in IRCD.get_clients(local=1, user=1, cap=client_cap) if c != client)
        for b_client in target_clients:
            if b_client in sent_clients:
                continue
            for channel in IRCD.get_channels():
                if (not channel.find_member(client) and client != IRCD.me) or not channel.find_member(b_client):
                    continue
                if not channel.user_can_see_member(b_client, client) or not channel.client_has_seen(b_client, client):
                    continue
                b_client.send(mtags, data)
                sent_clients.add(b_client)
                break

    @staticmethod
    def get_snomask(flag: str):
        return next((sn for sn in Snomask.table if sn.flag == flag), 0)

    @staticmethod
    def send_snomask(client: "Client", flag: str, data: str, sendsno: int = 1):
        if not (snomask := IRCD.get_snomask(flag)):
            return

        data = data.removeprefix(':')
        source = client if client == IRCD.me or client.server else client.uplink
        for c in (c for c in IRCD.get_clients(local=1, usermodes='s') if snomask.flag in c.user.snomask):
            if Batch := IRCD.get_attribute_from_module("Batch", package="modules.ircv3.batch"):
                Batch.check_batch_event(mtags=c.mtags, started_by=source, target_client=c, event="netjoin")
            c.send([], f":{source.name} NOTICE {c.name} :{data}")

        if snomask.is_global and sendsno:
            IRCD.send_to_servers(client, [], f":{source.id} SENDSNO {flag} :{data}")

    @staticmethod
    def server_notice(client: "Client", data: str):
        if client.server or not client.local:
            return
        client.send([], f":{client.uplink.name} NOTICE {client.name} :{data}")

    @staticmethod
    def send_oper_override(client: "Client", data: str) -> None:
        override_string = f"*** OperOverride: {client.name} ({client.user.username}@{client.user.realhost}) " + data
        IRCD.log(client, "info", "oper", "OPER_OVERRIDE", override_string, sync=1)

    @staticmethod
    def cli_resp(data: str) -> None:
        if data == '1':
            return
        for line in data.split('\n'):
            logging.error(line)

    @staticmethod
    def debug_freeze(func=None, *, debug=0):
        def decorator(fn):
            def wrapper(*args, **kwargs):
                debug and logging.debug(f"Calling {fn.__name__}()...")
                start = time()
                result = fn(*args, **kwargs)
                duration = time() - start
                is_threaded = threading.current_thread() is not threading.main_thread()
                debug and duration >= 0.5 and logging.warning(f"{fn.__name__}() took {duration:.3f}s (Threaded: {is_threaded})")
                return result

            return wrapper

        return decorator(func) if func else decorator

    @staticmethod
    def parallel(func=None, *, delay=0.0):
        delay = func if isinstance(func, (int, float)) and func is not None else delay

        def decorator(fn):
            def wrapper(*args, **kwargs):
                def delayed_target():
                    delay > 0 and Event().wait(delay)
                    fn(*args, **kwargs)

                IRCD.executor.submit(delayed_target)

            return wrapper

        return decorator(func) if func is not None and not isinstance(func, (int, float)) else decorator

    @staticmethod
    def ref_counts(target_obj, show_local: bool = False):
        """
        Finds and logs only the IDENTIFIABLE, named referrers to a given object.

        Any referrer for which a name cannot be found (e.g., a temporary list or
        an internal artifact) is treated as a local reference and ignored by default.

        Args:
            target_obj: The object to investigate.
            show_local: If True, will also show referrers for which no name could be
                        found, labeling them as "Unnamed". Defaults to False.
        """

        obj_repr = repr(target_obj)
        logging.debug(f"--- Analyzing referrers for {obj_repr[:200]} ---")

        gc.collect()
        all_referrers = gc.get_referrers(target_obj)
        internal_locals_id = id(locals())
        external_referrers = [r for r in all_referrers if id(r) != internal_locals_id]
        identified_referrers = []
        caller_frame = None

        try:
            caller_frame = inspect.currentframe().f_back
        except Exception:
            pass

        for referrer in external_referrers:
            found_locations = []
            if caller_frame:
                for name, obj in caller_frame.f_locals.items():
                    if obj is referrer:
                        found_locations.append(f"Caller's local variable: '{name}'")
                for name, obj in caller_frame.f_globals.items():
                    if obj is referrer and f"Caller's local variable: '{name}'" not in found_locations:
                        found_locations.append(f"Global variable: '{name}'")

            if not found_locations:
                gc.collect()
                for container_obj in gc.get_objects():
                    if hasattr(container_obj, '__dict__'):
                        for attr_name, attr_value in container_obj.__dict__.items():
                            if attr_value is referrer:
                                container_repr = f"<{type(container_obj).__name__} at {id(container_obj):#x}>"
                                found_locations.append(f"Attribute '{attr_name}' on object {container_repr}")

            identified_referrers.append((referrer, sorted(list(set(found_locations)))))

        final_results = []
        for referrer, locations in identified_referrers:
            if locations:
                final_results.append((referrer, locations))
            elif show_local:
                final_results.append((referrer, ["Unnamed (likely a temporary or internal object)"]))

        if not final_results:
            logging.debug("Object has no identifiable external referrers.")
            logging.debug("--- End of analysis ---")
            return

        logging.debug(f"Found {len(final_results)} identifiable referrer(s):")

        for i, (referrer, locations) in enumerate(final_results, 1):
            is_last = (i == len(final_results))
            prefix = '└──' if is_last else '├──'

            referrer_preview = repr(referrer)
            if len(referrer_preview) > 150:
                referrer_preview = referrer_preview[:150] + "..."
            logging.debug(f"{prefix} Referrer: a {type(referrer).__name__} | Content: {referrer_preview}")

            name_prefix = '   ' if is_last else '│  '
            for location in locations:
                logging.debug(f"{name_prefix}└── Location: {location}")

        logging.debug("--- End of analysis ---")


@dataclass
class ModData:
    name: str = ''
    value: str = ''
    sync: int = 0

    @staticmethod
    def get_from_client(client: "Client", name: str):
        return client.moddata.get(name, 0)

    @staticmethod
    def add_to_client(client: "Client", name: str, value: str, sync: int = 1):
        if not (md := ModData.get_from_client(client, name)):
            md = ModData(name=name, value=value, sync=sync)
            client.moddata[name] = md
        elif md.value != value:
            md.value = value
        if md.sync and client.id and client.registered:
            IRCD.send_to_servers(client, mtags=[], data=f":{client.uplink.id} MD client {client.id} {md.name} :{md.value}")

    @staticmethod
    def remove_from_client(client: "Client", name: str):
        if md := ModData.get_from_client(client, name):
            del client.moddata[md.name]
            if md.sync:
                IRCD.send_to_servers(client, mtags=[], data=f":{client.uplink.id} MD client {client.id} {md.name} :")


@dataclass
class Capability:
    table: ClassVar[list] = []

    name: str = ''
    value: str = ''

    @staticmethod
    def find_cap(capname):
        return next((c for c in Capability.table if c.name.lower() == capname.lower()), 0)

    @staticmethod
    def add(capname, value=None):
        if not Capability.find_cap(capname) and (cap := Capability(name=capname, value=value)):
            Capability.table.append(cap)
            for client in [c for c in IRCD.get_clients(local=1, cap="cap-notify")]:
                client.send([], f":{IRCD.me.name} CAP {client.name} NEW :{cap.string}")

    @staticmethod
    def remove(capname):
        if cap := Capability.find_cap(capname):
            Capability.table.remove(cap)
            for client in [c for c in IRCD.get_clients(local=1, cap="cap-notify")]:
                client.send([], f":{IRCD.me.name} CAP {client.name} DEL :{cap.string}")

    @property
    def string(self):
        return f"{self.name}{'=' + self.value if self.value else ''}"

    def __repr__(self):
        return f"<Capability '{self.string}'>"


@dataclass
class Stat:
    table: ClassVar[list] = []

    module: "Module" = None  # noqa: F821
    func: Callable = None
    letter: str = ''
    desc: str = ''

    @staticmethod
    def add(module, func, letter, desc):
        if Stat.get(letter):
            logging.error(f"Attempting to add duplicate STAT: {letter}")
            if not IRCD.rehashing:
                sys.exit()
            return
        Stat.table.append(Stat(module=module, func=func, letter=letter, desc=desc))

    @staticmethod
    def get(letter):
        return next((s for s in Stat.table if s.letter == letter), 0)

    def show(self, client):
        if self.func(client) != -1:
            client.sendnumeric(Numeric.RPL_ENDOFSTATS, self.letter)
            IRCD.send_snomask(client, 's', f"* Stats \"{self.letter}\" requested "
                                           f"by {client.name} ({client.user.username}@{client.user.realhost})")


def init_core_classes():
    from handle.client import Client
    from handle.channel import Channel, Channelmode
    core = sys.modules[__name__]
    core.Client = Client
    core.Channel = Channel
    core.Channelmode = Channelmode
