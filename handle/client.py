import gc
import ipaddress
import random
import string
import socket
import selectors
from time import time
from typing import ClassVar
from dataclasses import dataclass, field
from datetime import datetime
import concurrent.futures

import OpenSSL

from classes.data import Flag, Hook, Numeric, Isupport
from handle.functions import logging, ip_to_base64
from handle.core import IRCD, ModData, Command, Swhois
from handle.channel import Channel

Allow: type["Allow"]
ConnectClass: type["ConnectClass"]
Operclass: type["Operclass"]


class ClientList(list):
    def __init__(self, iterable=None):
        super().__init__(iterable or [])

    def remove(self, client):
        super().remove(client)
        IRCD.client_by_id.pop(client.id.lower(), None)
        if not client.has_flag(Flag.CLIENT_NICK_COLLISION):
            IRCD.client_by_name.pop(client.name.lower(), None)


@dataclass
class User:
    account: str = '*'
    modes: str = ''
    operlogin: str = None  # The oper account as defined in confg.
    operclass: "Operclass" = None
    server: "Server" = None
    username: str = ''
    realhost: str = ''
    vhost: str = '*'
    cloakhost: str = ''
    snomask: str = ''
    swhois: list = field(default_factory=list)  # Swhois dataclasses
    away: str = ''
    oper = None

    @property
    def host(self):
        return self.vhost if 'x' in self.modes else self.realhost


@dataclass
class Server:
    user = None
    mtags = []
    recv_mtags = []
    synced: int = 0
    authed: int = 0
    squit: int = 0
    registered: int = 1
    creationtime: int = int(time())
    lag: int = 0
    link = None

    def flood_safe_off(self):
        pass

    def flood_safe_on(self):
        pass

    def is_stealth(self):
        # Never true.
        return 0

    def sendnumeric(self, replycode, *args):
        pass

    def has_permission(self, check_path: str) -> int:
        return 1

    @property
    def local(self):
        return self == IRCD.me

    @property
    def is_local_user(self):
        return 0

    @property
    def fullrealhost(self):
        if self == IRCD.me:
            return IRCD.me.name


@dataclass(eq=False)
class Client:
    table: ClassVar[ClientList] = ClientList()
    server: "Server" = None
    user: "User" = None
    local: "LocalClient" = None
    class_: "ConnectClass" = None
    direction: "Client" = None
    uplink: "Client" = None
    id: str = ''  # UID for users, SID for servers
    flags: int = 0
    _name: str = '*'
    info: str = ''  # GECOS/realname
    ip: str = ''
    port: int = 0
    hopcount: int = 0
    moddata: dict = field(default_factory=dict)
    # MessageTag objects this client has generated.
    mtags: list = field(default_factory=list)
    recv_mtags: list = field(default_factory=list)
    idle_since: int = int(time())
    creationtime: int = int(time())
    last_ping_sent: int = 0
    last_command: str = ''
    lag: int = 0
    webirc: int = 0
    websocket: int = 0
    remember = dict(host='', cloakhost='', vhost='', ident='', nick='')
    hostname_future: concurrent.futures.Future = None
    hostname_future_submit_time: int = 1
    exit_time: float = 0

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        IRCD.client_by_name.pop(self.name.lower(), None)
        self._name = value
        IRCD.client_by_name[value.lower()] = self

    @property
    def registered(self):
        return self.has_flag(Flag.CLIENT_REGISTERED)

    @property
    def fullmask(self):
        return f"{self.name}!{self.user.username}@{self.user.host}" if self.user else self.name

    @property
    def fullrealhost(self):
        return f"{self.name}!{self.user.username or '*'}@{self.user.realhost or '*'}" if self.user else self.name

    def is_uline(self):
        return any(uline.lower() == self.uplink.name.lower() for uline in IRCD.get_setting("ulines"))

    def is_service(self):
        services = IRCD.get_setting("services")
        return services.lower() == self.uplink.name.lower()

    def is_local_user(self):
        return self.user and self.local

    def channels(self):
        return [channel for channel in Channel.table if self in channel.member_by_client]

    def set_host(self, host: str):
        clean_host = ''.join(c for c in host if c.lower() in IRCD.HOSTCHARS)
        if not clean_host or clean_host == self.user.vhost:
            return 0

        old_ident = self.remember.get("ident") or self.user.username
        old_host = self.remember.get("host") or self.user.host
        old_mask = f"{self.name}!{old_ident}@{old_host}"

        self.user.vhost = clean_host

        new_mask = f"{self.name}!{self.user.username}@{self.user.host}"
        if old_mask == new_mask:
            return 0

        if self.local:
            self.sendnumeric(Numeric.RPL_HOSTHIDDEN, self.user.host)

        IRCD.send_to_local_common_chans(self, [], client_cap="chghost", data=f":{old_mask} CHGHOST {self.user.username} {self.user.host}")
        IRCD.run_hook(Hook.USERHOST_CHANGE, self, old_ident, old_host)

        self.remember["ident"] = self.user.username
        self.remember["host"] = self.user.host

        return 1

    def get_ext_info(self) -> str:
        info_parts = []
        if self.user.vhost:
            info_parts.append(f"vhost: {self.user.vhost}")
        if self.class_:
            info_parts.append(f"class: {self.class_.name}")

        if self.user.account != '*':
            info_parts.append(f"account: {self.user.account}")

        metadata_fields = {
            "operlogin": "operlogin",
            "tls-cipher": "secure",
            "country": "country"
        }

        for key, label in metadata_fields.items():
            if value := self.get_md_value(key):
                info_parts.append(f"{label}: {value}")

        return ''.join(f" [{part}]" for part in info_parts)

    def handshake_finished(self) -> int:
        if self.has_flag(Flag.CLIENT_EXIT):
            return 0

        for delay in IRCD.delayed_connections:
            if delay[0] == self:
                return 0

        if not self.has_flag(Flag.CLIENT_HOST_DONE):
            return 0

        for result, callback in Hook.call(Hook.IS_HANDSHAKE_FINISHED, args=(self,)):
            if result == 0:
                return 0

        return 1 if self.user and self.name != '*' and self.user.username != '' and self.local.nospoof == 0 else 0

    def set_capability(self, capname) -> int:
        if not self.local or self.has_capability(capname):
            return 0
        self.local.caps.append(capname)
        return 1

    def remove_capability(self, capname) -> int:
        if not self.local or not self.has_capability(capname):
            return 0
        self.local.caps.remove(capname)
        return 1

    def has_capability(self, cap: str) -> bool:
        return self.local and cap in self.local.caps

    def has_permission(self, permission_path: str) -> int:
        if self == IRCD.me or self.server or not self.local or not self.user or self.has_flag(Flag.CLIENT_CMD_OVERRIDE):
            return 1
        if not self.user.operlogin or 'o' not in self.user.modes:
            return 0
        return self.user.operclass.has_permission(permission_path)

    def has_modes_any(self, modes: str) -> bool:
        return 0 if not self.user else any(mode in self.user.modes for mode in modes)

    def sendnumeric(self, replycode: int, *args: str) -> None:
        if self.is_local_user():
            reply_num, reply_string = replycode
            self.send(mtags=self.mtags, data=f":{IRCD.me.name} {str(reply_num).rjust(3, '0')} {self.name} {reply_string.format(*args)}")

    def set_class_obj(self, client_class_obj):
        self.class_ = client_class_obj
        self.add_md("class", client_class_obj.name)

    def setinfo(self, info, change_type: str) -> int:
        if change_type not in ["host", "ident", "gecos"]:
            logging.error(f"Incorrect type received in setinfo(): {change_type}")
            return 0

        try:
            if change_type in ["host", "ident"]:
                if not (clean_info := ''.join(c for c in info if c.lower() in IRCD.HOSTCHARS)):
                    return 0
                info = clean_info
                if change_type == "host":
                    self.set_host(host=info)
                else:
                    self.user.username = info

            # Handle gecos/realname changes
            else:
                if not (clean_info := ''.join(c for c in info if c.lower() in IRCD.HOSTCHARS + ' ')):
                    return 0
                self.info = clean_info
                if self.local:
                    IRCD.server_notice(self, f"*** Your realname is now \"{self.info}\"")
                    self.has_capability("setname") and self.send([], f":{self.fullmask} SETNAME :{self.info}")

                IRCD.send_to_local_common_chans(self, [], client_cap="setname", data=f":{self.fullmask} SETNAME :{self.info}")
                IRCD.run_hook(Hook.REALNAME_CHANGE, self, self.info)

            return 1

        except Exception as ex:
            logging.exception(ex)
            return 0

    def sync(self, server=None, cause=None):
        def send(tags, data):
            if server:
                server.send(tags, data)
            else:
                IRCD.send_to_servers(self, tags, data)

        if not IRCD.get_clients(local=1, server=1) or not self.user:
            return

        s2smd_tags = []
        if MessageTag := IRCD.get_attribute_from_module("MessageTag", package="modules.ircv3.messagetags"):
            if s2stag := MessageTag.find_tag("s2s-md"):
                for _, md in self.moddata.items():
                    tag = s2stag(value=md.value)
                    tag.name = f"{s2stag.name}/{md.name}"
                    s2smd_tags.append(tag)

        if not self.local and self.uplink.has_flag(Flag.CLIENT_EXIT):
            return logging.warning(f"Not syncing user {self.name} because its uplink server {self.uplink.name} exitted abruptly.")

        if self.name == '*':
            return logging.error(f"Tried to sync user {self.id} but it has no nickname yet?")

        sync_modes = ''.join(mode for mode in self.user.modes if (umode := IRCD.get_usermode_by_flag(mode)) and umode.is_global)
        binip = ip_to_base64(self.ip) if self.ip.replace('.', '').isdigit() else self.ip
        data = (f":{self.uplink.id} UID {self.name} {self.hopcount + 1} {self.creationtime} {self.user.username} {self.user.realhost} "
                f"{self.id} {self.user.account} +{sync_modes} {self.user.vhost} {self.user.cloakhost} {binip} :{self.info}")

        send(s2smd_tags, data)

        for _, md in self.moddata.items():
            send([], f":{self.uplink.id} MD client {self.id} {md.name} :{md.value}")

        if self.user.away:
            send([], f":{self.id} AWAY :{self.user.away}")

        for swhois in self.user.swhois:
            send([], f":{IRCD.me.id} SWHOIS {self.id} + {swhois.tag} :{swhois.line}")

        IRCD.run_hook(Hook.SERVER_UID_OUT, self, server)

    def remove_user(self, reason):
        if self.local:
            IRCD.local_user_count -= 1
        IRCD.global_user_count -= 1

        if self.registered and not self.is_uline() and (self.local or (not self.uplink.server.squit and self.uplink.server.synced)):
            event = "LOCAL_USER_QUIT" if self.local else "REMOTE_USER_QUIT"
            IRCD.log(self, "info", "quit", event,
                     f"*** Client exiting: {self.name} ({self.user.username}@{self.user.realhost}) [{self.ip}] ({reason})", sync=0)
            """
            Don't broadcast this user QUIT to other servers if its server is quitting or if the user has been killed.
            """
            if not self.is_killed():
                IRCD.send_to_servers(self, self.mtags, f":{self.id} QUIT :{reason}")

        for client in IRCD.get_clients(local=1):
            if IRCD.common_channels(self, client) and (Batch := IRCD.get_attribute_from_module("Batch", package="modules.ircv3.batch")):
                Batch.check_batch_event(mtags=self.mtags, started_by=self.direction, target_client=client, event="netsplit")

        if not self.uplink.server.squit:
            IRCD.new_message(self)

        IRCD.send_to_local_common_chans(self, self.mtags, client_cap=None, data=f":{self.name}!{self.user.username}@{self.user.host} QUIT :{reason}")

        for channel in list(Channel.table):
            if channel.find_member(self):
                channel.remove_client(self)

    def server_exit(self, reason, end_batch=1):
        def do_end_batch(batch_type):
            if Batch:
                started_by = self if self.local else self.uplink
                for batch in Batch.pool:
                    if batch.started_by in [started_by, started_by.direction] and batch.batch_type == batch_type:
                        batch.end()

        if not self.server:
            logging.error(f"server_exit() called on non-server client: {self.name}")
            return

        # noinspection PyPep8Naming
        Batch = IRCD.get_attribute_from_module("Batch", package="modules.ircv3.batch")
        netsplit_reason = f"{self.name} {self.uplink.name}"
        # End the netjoin batch if it hasn't been ended by EOS due to a sudden connection drop.
        do_end_batch("netjoin")

        if self.server.authed:
            if self.local:
                IRCD.log(self.uplink, "error", "link", "LINK_LOST", f"Lost connection to server {self.name}: {reason}", sync=0)
        else:
            if self.local and not self.local.incoming and not self.server.link.auto_connect:
                IRCD.log(IRCD.me, "error", "link", "LINK_OUT_FAIL", f"Unable to connect to {self.name}: {reason}", sync=0)
            IRCD.do_delayed_process()

        if self.server.authed:
            logging.debug(f"[server_exit()] Broadcasting to all other servers that server {self.name} has quit: {reason}")
            IRCD.send_to_servers(self, [], f"SQUIT {self.name} :{reason.removeprefix(':').strip()}")

        if Batch and not Batch.find_batch_by(self.direction):
            Batch.create_new(started_by=self.direction, batch_type="netsplit", additional_data=netsplit_reason)

        self.server.squit = 1
        for remote_client in [c for c in Client.table if c.uplink == self]:
            if remote_client.server:
                remote_client.exit(netsplit_reason, server_exit=0)
                remote_client.server_exit(reason, end_batch=0)
            else:
                remote_client.exit(netsplit_reason)

        if self in IRCD.send_after_eos:
            del IRCD.send_after_eos[self]

        if end_batch:
            do_end_batch("netsplit")

        IRCD.run_hook(Hook.SERVER_DISCONNECT, self)

    def kill(self, reason: str, killed_by=None) -> None:
        if not self.user:
            return logging.error(f"Cannot use kill() on server! Reason given: {reason}")

        if self.local:
            self.local.recvbuffer.clear()

        self.add_flag(Flag.CLIENT_KILLED)

        killed_by = killed_by or IRCD.me
        event = "LOCAL_KILL" if self.local else "GLOBAL_KILL"
        IRCD.log(self, "info", "kill", event,
                 f"*** Received kill msg for {self.name} ({self.user.username}@{self.user.realhost}) "
                 f"Path {killed_by.name} ({reason})", sync=0)

        if self.local:
            fullmask = killed_by.fullmask if killed_by != IRCD.me else IRCD.me.name
            self.sendnumeric(Numeric.RPL_TEXT, f"[{killed_by.name}] {reason}")
            self.send([], f":{fullmask} KILL {self.name} :{reason}")

        self.exit(f"Killed by {killed_by.name} ({reason})")
        IRCD.send_to_servers(killed_by, mtags=[], data=f":{killed_by.id} KILL {self.id} :{reason}")

    @IRCD.debug_freeze
    def exit(self, reason: str, sock_error: int = 0, server_exit: int = 1) -> None:
        if IRCD.current_link_sync == self:
            IRCD.current_link_sync = None

        if self not in Client.table or self.has_flag(Flag.CLIENT_EXIT):
            return

        Client.table.remove(self)
        self.add_flag(Flag.CLIENT_EXIT)
        self.exit_time = time()

        if self.server and server_exit:
            self.server_exit(reason)

        if self.user and self.registered:
            self.remove_user(reason)

        if self.local:
            if self.local.sendbuffer:
                self.direct_send(self.local.sendbuffer)

            IRCD.local_client_count -= 1
            IRCD.remove_delay_client(self)

            self.local.recvbuffer.clear()
            self.local.backbuffer.clear()
            self.local.sendq_buffer.clear()
            self.local.sendbuffer = ''
            self.local.temp_recvbuffer = ''
            if self.hostname_future and not self.hostname_future.done():
                self.hostname_future.cancel()
            self.hostname_future = None

            if reason and self.user and self.local.handshake and not sock_error:
                self.direct_send(f"ERROR :Closing link: {self.name}[{self.user.realhost or self.ip}] {reason}")

            try:
                IRCD.selector.unregister(self.local.socket)
            except KeyError:
                pass

            IRCD.client_by_sock.pop(self.local.socket, None)
            try:
                if not isinstance(self.local.socket, OpenSSL.SSL.Connection):
                    self.local.socket.shutdown(socket.SHUT_WR)
                else:
                    try:
                        self.local.socket.shutdown()
                    except OpenSSL.SSL.Error:
                        pass

            except (OSError, OpenSSL.SSL.Error, OpenSSL.SSL.SysCallError):
                pass
            except Exception as ex:
                logging.exception(ex)

            IRCD.pending_close_clients.append(self)

        if self.registered and self.user:
            hook = Hook.LOCAL_QUIT if self.local else Hook.REMOTE_QUIT
            IRCD.run_hook(hook, self, reason)

    def cleanup(self):
        IRCD.pending_close_clients.remove(self)
        self.local.socket.close()
        gc.collect()
        # IRCD.ref_counts(self)

    def is_killed(self):
        return self.has_flag(Flag.CLIENT_KILLED)

    def is_shunned(self):
        return self.has_flag(Flag.CLIENT_SHUNNED)

    def is_stealth(self):
        return 0

    def add_flag(self, flag):
        self.flags |= flag

    def del_flag(self, flag):
        self.flags &= ~flag

    def has_flag(self, flag):
        return bool(self.flags & flag)

    def add_swhois(self, line: str, tag: str, remove_on_deoper: int = 0):
        Swhois.add_to_client(self, line, tag=tag, remove_on_deoper=remove_on_deoper)

    def del_swhois(self, line: str):
        Swhois.remove_from_client(self, line)

    def add_md(self, name: str, value: str, sync: int = 1):
        name, value = name.replace(' ', '_'), value.replace(' ', '_')
        ModData.add_to_client(self, name, value, sync)

    def del_md(self, name: str):
        name = name.replace(' ', '_')
        ModData.remove_from_client(self, name)

    def get_md_value(self, name: str):
        name = name.replace(' ', '_')
        return (md := ModData.get_from_client(self, name)) and md.value

    def seconds_since_signon(self):
        return int(time()) - self.creationtime

    def flood_safe_on(self):
        self.add_flag(Flag.CLIENT_USER_FLOOD_SAFE)

    def flood_safe_off(self):
        self.del_flag(Flag.CLIENT_USER_FLOOD_SAFE)

    def is_flood_safe(self):
        return self.has_flag(Flag.CLIENT_USER_FLOOD_SAFE)

    def add_flood_penalty(self, penalty: int):
        if not self.local or self.is_flood_safe():
            return
        self.local.flood_penalty += penalty

    def check_flood(self):
        if self.is_flood_safe():
            self.local.sendq_buffer.clear()
            return

        if not self.local or not self.user:
            return

        if not self.local.flood_penalty_time:
            self.local.flood_penalty_time = int(time())

        sendq = getattr(self.class_, "sendq", 65536)
        recvq = getattr(self.class_, "recvq", 65536)

        divisor = 2 if not self.registered else 1
        buffer_len_recv = sum(len(e[1]) for e in self.local.backbuffer) // divisor
        buffer_len_send = sum(len(e[1]) for e in self.local.sendq_buffer) // divisor

        if buffer_len_recv >= recvq or buffer_len_send >= sendq:
            flood_type = "recvq" if buffer_len_recv >= recvq else "sendq"
            flood_limit = recvq if flood_type == "recvq" else sendq
            flood_amount = buffer_len_recv if flood_type == "recvq" else buffer_len_send
            if self.registered:
                msg = (f"*** Flood -- {self.name} ({self.user.username}@{self.user.realhost}) has reached their max "
                       f"{'RecvQ' if flood_type == 'recvq' else 'SendQ'} ({flood_amount}) while the limit is {flood_limit}")
                IRCD.log(self, "warn", "flood", f"FLOOD_{flood_type.upper()}", msg, sync=1)

            self.exit("Excess Flood")
            return

        cmd_len = len(self.local.recvbuffer) // divisor
        max_cmds = int(recvq / 50) // divisor
        if cmd_len >= max_cmds:
            if self.registered:
                msg = (f"*** Buffer Flood -- {self.name} ({self.user.username}@{self.user.realhost}) has reached "
                       f"their max buffer length ({cmd_len}) while the limit is {max_cmds}")
                IRCD.log(self, "warn", "flood", f"FLOOD_BUFFER_EXCEEDED", msg, sync=1)
            self.exit("Excess Flood")
            return

        flood_penalty_threshold = 10_000_000 if 'o' in self.user.modes else (1_000_000 // divisor)
        if int(time()) - self.local.flood_penalty_time >= 60:
            self.local.flood_penalty = 0
            self.local.flood_penalty_time = 0

        if self.local.flood_penalty >= flood_penalty_threshold:
            if self.registered:
                msg = (f"*** Flood -- {self.name} ({self.user.username}@{self.user.realhost}) has reached "
                       f"their max flood penalty ({self.local.flood_penalty}) while the limit is {flood_penalty_threshold}")
                IRCD.log(self, "warn", "flood", f"FLOOD_PENALTY_LIMIT", msg, sync=1)
            self.exit("Excess Flood")

    def assign_host(self):
        if not self.user or self.user.realhost:
            return

        if ban := IRCD.is_ban_client("user", self):
            IRCD.server_notice(self, f"You are banned: {ban.reason}")
            self.exit(ban.reason)
            return

        if not IRCD.is_except_client("throttle", self):
            if throttle_setting := IRCD.get_setting("throttle"):
                throttle_threshold, throttle_time = map(int, throttle_setting.split(':'))
                if len(IRCD.throttle[self.ip]) >= throttle_threshold:
                    self.exit("Throttling - You are (re)connecting too fast")
                    return

                IRCD.throttle[self.ip].append(int(time()))

        realhost = self.ip
        cache_info = ''

        if IRCD.get_setting("resolvehost"):
            if cached := IRCD.hostcache.get(self.ip):
                realhost, cache_info = cached[1], " [cached]"

            else:
                self.hostname_future = IRCD.executor.submit(socket.gethostbyaddr, self.ip)
                self.hostname_future_submit_time = int(time())
                self.user.realhost = realhost
                self.user.cloakhost = self.user.vhost = IRCD.get_cloak(self)
                self.remember["cloakhost"] = self.user.cloakhost
                IRCD.server_notice(self, "*** Looking up your hostname...")
                return

        else:
            IRCD.server_notice(self, "*** Host resolution disabled, using IP address instead")

        if IRCD.get_setting("resolvehost"):
            IRCD.server_notice(self, f"*** Found your hostname: {realhost}{cache_info}")

        self.user.realhost = realhost
        self.user.cloakhost = self.user.vhost = IRCD.get_cloak(self)
        self.remember["cloakhost"] = self.user.cloakhost
        self.add_flag(Flag.CLIENT_HOST_DONE)

    def add_user_modes(self, modes):
        if not self.local:
            return

        if valid_modes := [mode for mode in modes if IRCD.get_usermode_by_flag(mode) and mode not in self.user.modes]:
            current_modes = self.user.modes
            new_modes = ''.join(valid_modes)
            self.user.modes += new_modes
            self.send([], f":{self.name} MODE {self.name} +{new_modes}")
            if self.registered:
                IRCD.send_to_servers(self, [], f":{self.id} MODE {self.name} +{new_modes}")

    def assign_class(self):
        """ Assign class only after registration is complete. """

        for allow in IRCD.configuration.allow:
            if not allow.mask.is_match(self):
                continue

            if allow.password and self.local.authpass != allow.password:
                if "reject-on-auth-fail" in allow.options:
                    self.sendnumeric(Numeric.ERR_PASSWDMISMATCH)
                    self.exit("Invalid password")
                    return 0
                continue

            if "tls" in allow.options and not self.local.tls:
                continue

            if not (connectclass := IRCD.get_class_from_name(allow.connectclass_name)):
                logging.debug(f"Skipping non-existing class '{allow.connectclass_name}' in allow-block.")
                continue

            ip_count = sum(1 for c in IRCD.get_clients(local=1) if c.class_ == connectclass and c.ip == self.ip)
            if ip_count > allow.maxperip:
                self.exit("Maximum connections from this IP reached for this class.")
                return 0

            class_count = sum(1 for c in IRCD.get_clients(local=1) if c.class_ == connectclass)
            if class_count > connectclass.max:
                self.exit("Maximum connections for this class reached")
                return 0

            self.set_class_obj(connectclass)
            return 1

        if not self.class_:
            self.exit(f"You are not authorised to connect to this server")
            return 0

        return 1

    def register_user(self):
        if not self.assign_class():
            return

        self.welcome_user()

    def welcome_user(self):
        if self.registered:
            return

        for result, hook_obj in Hook.call(Hook.PRE_CONNECT, args=(self,)):
            if result == Hook.DENY:
                logging.debug(f"Connection process denied for user {self.name} by module: {hook_obj}")
                self.exit("Connection closed by server")
                return
            if result == Hook.ALLOW:
                """ A module explicitly allowed it. Not processing other modules. """
                break

        if self.has_flag(Flag.CLIENT_EXIT):
            return

        if self.local.tls and hasattr(self.local.socket, "get_cipher_name") and (cipher_name := self.local.socket.get_cipher_name()):
            cipher_version = self.local.socket.get_cipher_version()
            cipher_info = f"{cipher_version}-{cipher_name}"
            IRCD.server_notice(self, f"*** You are connected to {IRCD.me.name} with {cipher_info}")
            self.add_md("tls-cipher", cipher_info)

        IRCD.local_user_count += 1
        IRCD.maxusers = max(IRCD.maxusers, IRCD.local_user_count)
        IRCD.global_user_count += 1
        IRCD.maxgusers = max(IRCD.maxgusers, IRCD.global_user_count)

        self.creationtime = self.idle_since = int(time())
        self.sendnumeric(Numeric.RPL_WELCOME, IRCD.me.name, self.name, self.user.username, self.user.realhost)
        self.sendnumeric(Numeric.RPL_YOURHOST, IRCD.me.name, IRCD.version)
        created = datetime.fromtimestamp(IRCD.me.creationtime)
        self.sendnumeric(Numeric.RPL_CREATED, created.strftime("%a %b %d %Y"), created.strftime("%H:%M:%S %Z"))
        self.sendnumeric(Numeric.RPL_MYINFO, IRCD.me.name, IRCD.version, IRCD.get_umodes_str(), IRCD.get_chmodes_str())
        Isupport.send_to_client(self)
        self.sendnumeric(Numeric.RPL_HOSTHIDDEN, self.user.cloakhost)

        msg = f"*** Client connecting: {self.name} ({self.user.username}@{self.user.realhost}) [{self.ip}]{self.get_ext_info()}"
        IRCD.log(self, "info", "connect", "LOCAL_USER_CONNECT", msg, sync=0)

        Command.do(self, "LUSERS")
        Command.do(self, "MOTD")

        if conn_modes := IRCD.get_setting("modes-on-connect"):
            modes = {m for m in conn_modes if m.isalpha() and m not in self.user.modes}
            if self.local.tls:
                modes.add('z')
            if modes:
                self.add_user_modes(list(modes))

        self.sync(cause="welcome_user()")
        self.add_flag(Flag.CLIENT_REGISTERED)
        IRCD.run_hook(Hook.LOCAL_CONNECT, self)

    def handle_recv(self):
        if not self.has_flag(Flag.CLIENT_HANDSHAKE_FINISHED):
            """ First sockread. """
            self.add_flag(Flag.CLIENT_HANDSHAKE_FINISHED)

            if self.user and (ban := IRCD.is_ban_client("user", self)):
                """
                Hostname check.
                We run this here because now we can check against exceptions from certfp.
                """
                IRCD.server_notice(self, f"You are banned: {ban.reason}")
                self.exit(ban.reason)
                return

        if self.has_flag(Flag.CLIENT_EXIT):
            return

        current_time = time()
        self.local.last_msg_received = int(current_time)

        try:
            for line in list(self.local.recvbuffer):
                time_to_execute, recv = line
                if self.user and time_to_execute - current_time > 0 and 'o' not in self.user.modes:
                    continue

                cmd = recv.split()[0].upper()
                if self.user:
                    self.add_flood_penalty(100)

                if (self.server and IRCD.current_link_sync and
                        IRCD.current_link_sync != self and
                        cmd != "SQUIT" and
                        self not in IRCD.process_after_eos):
                    IRCD.process_after_eos.append(self)
                    logging.debug(f"Deferring {self.name} until sync with {IRCD.current_link_sync.name} completes")
                    continue

                self.local.recvbuffer.remove(line)

                if not (recv := recv.strip()):
                    continue

                parsed_tags = []
                if recv.startswith('@'):
                    tag_data = recv[1:].split()[0].split(';')
                    parsed_tags = IRCD.parse_remote_mtags(self, tag_data)
                    recv = ' '.join(recv.split(' ')[1:]) if self.user else recv[recv.find(" :") + 1:]
                    if not recv.strip():
                        continue

                source_client = self
                if recv.startswith(':') and len(recv) > 1:
                    parts = recv[1:].split(' ', maxsplit=1)
                    source_id = parts[0]
                    recv = parts[1]

                    if self.server:
                        found_client = IRCD.find_client(source_id)
                        if not found_client and self.server.authed:
                            logging.warning(f"Unknown server message from {source_id}: {recv}")
                            continue

                        source_client = found_client or self

                # source_client = self
                # if recv.startswith(':') and len(recv) > 1:
                #     source_id = recv[1:].split()[0]
                #     if self.server:
                #         source_client = IRCD.find_client(source_id)
                #         if not source_client and self.server.authed:
                #             logging.warning(f"Unknown server message from {self.id}: {recv}")
                #             continue
                #         source_client = source_client or self
                #     recv = recv.split(' ', maxsplit=1)[1]

                seen = set()
                parsed_tags = [tag for tag in parsed_tags if not (tag.name in seen or seen.add(tag.name))]

                if self.server:
                    source_client.mtags = parsed_tags
                source_client.recv_mtags = parsed_tags

                recv = recv.split(' ')
                command = recv[0].upper()

                if (cmd := Command.find_command(source_client, command, *recv)) not in [0, 1]:
                    result, *args = cmd.check(source_client, recv)
                    if result != 0 and not self.server:
                        self.sendnumeric(result, *args)
                        source_client.recv_mtags.clear()
                        continue
                    cmd.do(source_client, *recv)
                elif cmd == 0 and not self.server:
                    self.sendnumeric(Numeric.ERR_UNKNOWNCOMMAND, command)
                    IRCD.run_hook(Hook.POST_COMMAND, self, recv[0], recv)
                    self.mtags.clear()
                    self.recv_mtags.clear()
                    self.flood_safe_off()

        except Exception as ex:
            logging.exception(ex)

    @IRCD.debug_freeze
    def send(self, mtags: list, data: str, call_hook=1):
        if not isinstance(data, str):
            logging.error(f"Wrong data type @ send(): {data}")
            return

        if (self.has_flag(Flag.CLIENT_EXIT) or self not in Client.table or not self.local or (
                not self.websocket and not (self.local.socket or self.local.socket.fileno() < 0))):
            return

        data = data.strip()
        if call_hook:
            data_list = data.split(' ')
            IRCD.run_hook(Hook.PACKET, IRCD.me, self.direction, self, data_list)
            data = ' '.join(data_list)
            if not data.strip():
                return

        if MessageTag := IRCD.get_attribute_from_module("MessageTag", package="modules.ircv3.messagetags"):
            if mtags := MessageTag.filter_tags(destination=self, mtags=mtags):
                data = f"@" + ';'.join([t.string for t in mtags]) + ' ' + data

        if not self.websocket:
            try:
                key = IRCD.selector.get_key(self.local.socket)
                current_events = key.events
                IRCD.selector.modify(self.local.socket, current_events | selectors.EVENT_WRITE, data=self)
            except (ValueError, OSError) as ex:
                self.exit(f"Write error: {str(ex)}")
                return

            if self.local.handshake:
                self.local.sendbuffer += data + "\r\n"
            else:
                self.direct_send(data)

        if self.user and 'o' not in self.user.modes:
            """ Keep the backbuffer entry duration based on the incoming data length. """
            delay = len(data) / 10
            sendq_buffer_time = time() + delay
            self.local.sendq_buffer.append([sendq_buffer_time, data])
            self.check_flood()

        if self.websocket and IRCD.websocketbridge:
            IRCD.websocketbridge.send_to_client(self, data)
            return

    @IRCD.debug_freeze
    def direct_send(self, data: str) -> None:
        """ Directly sends data to a socket. """
        debug_out = 0
        lines = [line for line in data.split('\n') if line.strip()]
        lines_sent = 0

        try:
            for line in lines:
                if self.websocket and IRCD.websocketbridge:
                    IRCD.websocketbridge.send_to_client(self, line)
                    lines_sent += 1
                    continue

                try:
                    sent = self.local.socket.send(bytes(line + "\r\n", "utf-8"))
                    self.local.bytes_sent += sent
                    self.local.messages_sent += 1

                    if self.user:
                        self.add_flood_penalty(100)

                    ignore_commands = ["ping", "pong", "privmsg", "notice", "tagmsg"]
                    if self.registered:
                        split_line = line.split()
                        for i in range(min(3, len(split_line))):
                            if split_line[i].lower() in ignore_commands:
                                debug_out = 0
                                break

                    if debug_out:
                        logging.debug(f"[OUT] {self.name}[{self.ip}] < {line}")

                    lines_sent += 1

                except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.SysCallError, OpenSSL.SSL.Error, BrokenPipeError, Exception) as ex:
                    break

        except (OpenSSL.SSL.SysCallError, OpenSSL.SSL.Error, BrokenPipeError, Exception) as ex:
            self.exit(f"Write error: {str(ex)}")
            return

        if lines_sent > 0:
            if lines_sent == len(lines):
                self.local.sendbuffer = ''
            else:
                self.local.sendbuffer = '\n'.join(lines[lines_sent:])

    def direct_send_old(self, data):
        """ Directly sends data to a socket. """

        debug_out = 0

        try:
            for line in [line for line in data.split('\n') if line.strip()]:
                if self.websocket and IRCD.websocketbridge:
                    IRCD.websocketbridge.send_to_client(self, line)
                    continue

                sent = self.local.socket.send(bytes(line + "\r\n", "utf-8"))
                self.local.bytes_sent += sent
                self.local.messages_sent += 1

                ignore_commands = ["ping", "pong", "privmsg", "notice", "tagmsg"]
                if self.registered:
                    split_line = line.split()
                    for i in range(min(3, len(split_line))):
                        if split_line[i].lower() in ignore_commands:
                            debug_out = 0
                            break

                if debug_out:
                    logging.debug(f"[OUT] {self.name}[{self.ip}] < {line}")

        except OpenSSL.SSL.WantReadError:
            """ Not ready to write yet. """
            return 0

        except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.SysCallError, OpenSSL.SSL.Error, BrokenPipeError, Exception) as ex:
            error_message = f"Write error: {str(ex)}"
            self.exit(error_message)

        return 1


@dataclass
class LocalClient:
    allow: "Allow" = None
    authpass: str = ''
    socket: socket = None
    caps: list = field(default_factory=list)
    tls: OpenSSL = None
    error_str: str = ''
    nospoof: str = ''
    last_msg_received: int = 0
    creationtime: int = int(time())
    flood_penalty: int = 0
    flood_penalty_time: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    incoming: int = 0
    protoctl: list = field(default_factory=list)
    recvbuffer: [] = field(repr=False, default_factory=list)  # This is data that the client sends to the server.
    sendbuffer: str = ''
    temp_recvbuffer: str = ''
    backbuffer: [] = field(repr=False, default_factory=list)
    sendq_buffer: [] = field(repr=False, default_factory=list)
    auto_connect: int = 0
    handshake: int = 0


def make_client(direction, uplink) -> Client | None:
    """
    direction           The locally connected server who introduced this client. For local clients this will be None.
    uplink              The server to which this client is uplinked. This can be this server, if it is a local client.
    """

    if direction and not direction.local:
        logging.error(
            f"Could not make_client(), 'direction' should be None (for locally accepted clients),"
            f"or a local client when creating a new remote client!")
        logging.error(f"Direction was: {direction.name}")
        exit()

    current_time = int(time())
    client = Client()
    client.direction = direction or uplink
    client.uplink = uplink
    client.creationtime = current_time

    if not direction:
        client.local = LocalClient()
        client.last_ping_sent = int(time() * 1000)
        client.local.last_msg_received = current_time
        client.local.creationtime = current_time
        IRCD.local_client_count += 1

    Client.table.append(client)
    return client


def make_server(client: Client):
    client.server = Server()
    if client.uplink == IRCD.me:
        client.direction = client
    return client


def cookie_helper(client):
    if client.local.nospoof:
        IRCD.server_notice(client, f"*** If you have registration timeouts, "
                                   f"use /quote PONG {client.local.nospoof} or /raw PONG {client.local.nospoof}")


@IRCD.debug_freeze
def make_user(client: Client):
    client.user = User()
    if client.local:
        client.id = IRCD.get_next_uid()
        IRCD.client_by_id[client.id.lower()] = client
        client.assign_host()
        client.local.nospoof = ''.join(random.choice(string.digits + string.ascii_uppercase) for _ in range(8))
        client.send([], f"PING :{client.local.nospoof}")
        IRCD.run_parallel_function(cookie_helper, args=(client,), delay=0.55)
    return client
