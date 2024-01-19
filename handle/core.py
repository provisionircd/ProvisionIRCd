import binascii
import datetime
import gc
import hashlib
import ipaddress
import itertools
import json
import logging
import os
import re
import random
import string
import time
import socket
import OpenSSL
from enum import Enum
from random import randrange
from sys import version
from threading import Thread
from time import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import NewType, ClassVar, Callable

import select
from _socket import gethostbyaddr

from handle.functions import is_match, IPtoBase64
from handle.logger import logging, IRCDLogger

gc.enable()

Client = NewType("Client", None)
LocalClient = NewType("LocalCLient", None)
User = NewType("User", None)
Server = NewType("Server", None)
Allow = NewType("Allow", None)
ConnectClass = NewType("ConnectClass", None)
Listen = NewType("Listen", None)
Link = NewType("Link", None)
Operclass = NewType("Operclass", None)
Module = NewType("Module", None)
IRCD = NewType("IRCD", None)

flag_idx = 100
hook_idx = 100


def flag():
    global flag_idx
    flag_idx += 1
    return flag_idx


def hook():
    global hook_idx
    hook_idx += 1
    return hook_idx


class Flag(Enum):
    CMD_UNKNOWN = flag()
    CMD_USER = flag()
    CMD_SERVER = flag()
    CMD_OPER = flag()

    CLIENT_SHUNNED = flag()
    CLIENT_ON_HOLD = flag()

    CLIENT_HANDSHAKE_FINISHED = flag()

    CLIENT_REGISTERED = flag()
    CLIENT_KILLED = flag()
    CLIENT_USER_FLOOD_SAFE = flag()
    CLIENT_USER_SAJOIN = flag()
    CLIENT_USER_SANICK = flag()


@dataclass(eq=False)
class Client:
    table: ClassVar[list] = []
    server: Server = None
    user: User = None
    local: LocalClient = None
    class_: ConnectClass = None
    direction: Client = None
    uplink: Server = None
    id: str = None  # UID for users, SID for servers
    flags: list = field(default_factory=list)
    name: str = '*'
    info: str = ''  # GECOS/realname
    ip: str = None
    port: int = 0
    hopcount: int = 0
    lastnick: int = 0
    moddata: list = field(default_factory=list)
    # MessageTag objects this client has generated.
    mtags: list = field(default_factory=list)
    recv_mtags: list = field(default_factory=list)
    idle_since: int = int(time())
    creationtime: int = int(time())
    last_ping_sent: int = 0
    last_command: str = ''
    lag: int = 0
    exitted: int = 0

    @property
    def registered(self):
        if Flag.CLIENT_REGISTERED in self.flags:
            return 1
        if not self.local:
            logging.warning(f"Remote client {self.name} is not marked as registered")

    @property
    def ulined(self):
        for uline in IRCD.get_setting("ulines"):
            if uline.lower() in [self.uplink.name.lower(), self.name.lower()]:
                return 1
        return 0

    @property
    def is_service(self):
        services = IRCD.get_setting("services")
        return services.lower() in [self.uplink.name.lower(), self.name.lower()]

    @property
    def channels(self):
        channels = []
        for channel in Channel.table:
            for member in channel.members:
                if member.client == self:
                    channels.append(channel)
                    break
        return channels

    @property
    def fullmask(self):
        if self.user:
            return f"{self.name}!{self.user.username}@{self.user.cloakhost}"
        else:
            return self.name

    @property
    def fullrealhost(self):
        if self.user:
            ident = self.user.username
            if not ident:
                ident = '*'
            return f"{self.name}!{ident}@{self.user.realhost if self.user.realhost else '*'}"
        else:
            return self.name

    def get_ext_info(self):
        ext_info = ''
        if self.class_:
            ext_info += f" [class: {self.class_.name}]"
        if self.user.account != '*':
            ext_info += f" [account: {self.user.account}]"
        if operlogin := self.get_md_value("operlogin"):
            ext_info += f" [operlogin: {operlogin}]"
        if cipher := self.get_md_value("tls-cipher"):
            ext_info += f" [secure: {cipher}]"
        if country := self.get_md_value("country"):
            ext_info += f" [country: {country}]"
        return ext_info

    def handshake_finished(self):
        if self.exitted:
            return 0
        for delay in IRCD.delayed_connections:
            if delay[0] == self:
                return 0
        for result, callback in Hook.call(Hook.IS_HANDSHAKE_FINISHED, args=(self,)):
            if result == 0:
                return 0

        if self.user:
            if self.name != '*' and self.user.username != '' and self.local.nospoof == 0:
                self.local.authpass = 0
                return 1
            return 0

    def has_capability(self, cap: str):
        if not self.local:
            return 0
        return cap in self.local.caps

    def has_permission(self, permission_path: str):
        if self.server or not self.local or not self.user:
            return 1
        if not self.user.operlogin or 'o' not in self.user.modes:
            return 0

        return self.user.operclass.has_permission(permission_path)

    def has_modes_any(self, modes: str):
        """
        Returns true when a user has any of the given modes.
        """
        if not self.user:
            return 0
        for mode in modes:
            if mode in self.user.modes:
                return 1
        return 0

    def has_modes_all(self, modes: str):
        """
        Returns true if the user has all of the given modes.
        """
        if not self.user:
            return 0
        for mode in modes:
            if mode not in self.user.modes:
                return 0
        return 1

    def sendnumeric(self, replycode, *args):
        if not self.user and not self.local or not hasattr(IRCD, "me"):
            return
        reply_num, reply_string = replycode
        reply_num = str(reply_num).rjust(3, '0')
        reply_string = reply_string.format(*args)
        numericmsg = f":{IRCD.me.name} {reply_num} {self.name} {reply_string}"
        self.send(mtags=[], data=numericmsg)

    def set_class_obj(self, client_class_obj):
        self.class_ = client_class_obj
        self.add_md("class", client_class_obj.name)

    def setinfo(self, info, t='') -> int:
        try:
            if not info or not t:
                return 0
            if t not in ['host', 'ident', 'gecos']:
                logging.error(f'Incorrect type received in setinfo(): {t}')
                return 0
            if self.registered and t in ['host', 'ident']:
                for c in str(info):
                    if c.lower() not in IRCD.HOSTCHARS:
                        info = info.replace(c, '')
                    if not info.strip():
                        return 0

            IRCD.new_message(self)
            if t in ["ident", "host"]:
                data = f":{self.fullmask} CHGHOST {info if t == 'ident' else self.user.username} {info if t == 'host' else self.user.cloakhost}"
                IRCD.send_to_local_common_chans(self, [], "chghost", data)
            else:  # Setname
                data = f":{self.fullmask} SETNAME :{info}"
                IRCD.send_to_local_common_chans(self, [], "setname", data)

            if t == 'host':
                if self.user.cloakhost != info:
                    self.user.cloakhost = info
                    self.sendnumeric(Numeric.RPL_HOSTHIDDEN, self.user.cloakhost)
                    logging.debug(f"[setinfo()] Changed host of {self.name} to: {self.user.cloakhost}")
            elif t == 'ident':
                self.user.username = info
            elif t == 'gecos':
                if self.info != info:
                    self.info = info
                    if self.local:
                        if self.has_capability("setname"):
                            self.send([], f":{self.name} SETNAME :{self.info}")
                        else:
                            IRCD.server_notice(self, f"*** Your realname is now \"{self.info}\"")
            return 1

        except Exception as ex:
            logging.exception(ex)
            return 0

    def sync(self, server=None, cause=None):
        if not IRCD.local_servers():
            return
        s2smd_tags = []
        if s2stag := MessageTag.find_tag("s2s-md"):
            for md in self.moddata:
                name = s2stag.name + '/' + md.name
                tag = s2stag(value=md.value)
                tag.name = name
                s2smd_tags.append(tag)

        if not self.user:
            return
        if not self.local and self.uplink.exitted:
            logging.warning(f"Not syncing user {self.name} because its uplink server {self.uplink.name} exitted abruptly.")
            return

        if self.name == '*':
            logging.error(f"Tried to sync user {self.id} but it has no nickname yet?")
            return

        logging.debug(f"Syncing user {self.name} to all locally connected servers.")
        if cause:
            logging.debug(f"Cause of {self.name} sync: {cause}")

        sync_modes = ''
        for mode in self.user.modes:
            umode = IRCD.get_usermode_by_flag(mode)
            if umode and umode.is_global:
                sync_modes += mode
        binip = IPtoBase64(self.ip) if self.ip.replace('.', '').isdigit() else self.ip
        data = f":{self.uplink.id} UID {self.name} {self.hopcount + 1} {self.creationtime} {self.user.username} {self.user.realhost} {self.id} {self.user.account} +{sync_modes} {self.user.cloakhost} {self.user.cloakhost} {binip} :{self.info}"
        if server:
            server.send(s2smd_tags, data)
        else:
            IRCD.send_to_servers(self, s2smd_tags, data)

        for md in self.moddata:
            data = f":{self.uplink.id} MD client {self.id} {md.name} :{md.value}"
            if server:
                server.send([], data)
            else:
                IRCD.send_to_servers(self, [], data)

        if self.user.away:
            data = f":{self.id} AWAY :{self.user.away}"
            if server:
                server.send([], data)
            else:
                IRCD.send_to_servers(self, [], data)

        for swhois in self.user.swhois:
            data = f":{IRCD.me.id} SWHOIS + {self.id} :{swhois.line}"
            if server:
                server.send([], data)
            else:
                IRCD.send_to_servers(self, [], data)

    def remove_user(self, reason):
        if self.local:
            IRCD.local_user_count -= 1
        IRCD.global_user_count -= 1

        if (self.local or not self.uplink.server.squit) and self.registered and not self.ulined:
            msg = f"*** Client exiting: {self.name} ({self.user.username}@{self.user.realhost}) [{self.ip}] ({reason})"
            event = "LOCAL_USER_QUIT" if self.local else "REMOTE_USER_QUIT"
            IRCD.log(self, "info", "quit", event, msg, sync=0)
            """
            Don't broadcast this user QUIT to other servers if its server is quitting or if the user has been killed.
            """
            if not self.is_killed():
                data = f":{self.id} QUIT :{reason}"
                IRCD.send_to_servers(self, self.mtags, data)

        for client in IRCD.local_clients():
            if IRCD.common_channels(self, client):
                Batch.check_batch_event(mtags=self.mtags, started_by=self.direction, target_client=client, event="netsplit")

        if not self.uplink.server.squit:
            IRCD.new_message(self)
        data = f":{self.name}!{self.user.username}@{self.user.cloakhost} QUIT :{reason}"
        IRCD.send_to_local_common_chans(self, self.mtags, client_cap=None, data=data)

        for channel in list(Channel.table):
            if channel.find_member(self):
                logging.debug(f"Removing client {self.name} (uplink={self.uplink.name}) from {channel.name}")
                channel.remove_client(self)

    def server_exit(self, reason):
        netsplit_reason = self.name + " " + self.uplink.name
        if not self.server:
            logging.error(f"server_exit() called on non-server client: {self.name}")
            return
        if self.server.synced:
            IRCD.log(self.uplink, "error", "link", "LINK_LOST", f"Lost connection to server {self.name}: {reason}", sync=0)
            if not Batch.find_batch_by(self):
                Batch.create_new(started_by=self, batch_type="netsplit", additional_data=netsplit_reason)
        else:
            if self.local and not self.local.incoming and not self.server.link.auto_connect:
                IRCD.log(IRCD.me, "error", "link", "LINK_OUT_FAIL", f"Unable to connect to {self.name}: {reason}", sync=0)

        if not self.server.synced:
            IRCD.do_delayed_process()

        if self.server.synced:
            try:
                self.server.squit = 1
                for remote_client in [c for c in Client.table if c.uplink == self]:
                    logging.debug(f"Exiting {remote_client.name} because it was uplinked to {self.name}")
                    remote_client.exit(netsplit_reason)
                if self.registered:
                    data = f"SQUIT {self.name} :{reason.removeprefix(':')}"
                    IRCD.send_to_servers(self, [], data)

            except Exception as ex:
                logging.exception(ex)

            if self in IRCD.send_after_eos:
                del IRCD.send_after_eos[self]

            IRCD.run_hook(Hook.SERVER_DISCONNECT, self)

        for batch in Batch.pool:
            if batch.started_by == self and batch.batch_type == "netsplit":
                batch.end()

    def kill(self, reason: str, killed_by=None) -> None:
        if not self.user:
            return logging.error(f"Cannot use kill() on server! Reason given: {reason}")
        if self.local:
            self.local.recvbuffer = []
        if Flag.CLIENT_KILLED not in self.flags:
            self.flags.append(Flag.CLIENT_KILLED)
        try:
            if killed_by:
                path = killed_by.name
            else:
                killed_by = IRCD.me
                path = IRCD.me.name
            quitreason = f"Killed by {path} ({reason})"
            msg = f"*** Received kill msg for {self.name} ({self.user.username}@{self.user.realhost}) Path {path} ({reason})"
            event = "LOCAL_KILL" if self.local else "GLOBAL_KILL"
            IRCD.log(self, "info", "kill", event, msg, sync=0)
            if self.local:
                if killed_by == IRCD.me:
                    fullmask = IRCD.me.name
                else:
                    fullmask = killed_by.fullmask
                self.sendnumeric(Numeric.RPL_TEXT, f"[{path}] {reason}")
                data = f":{fullmask} KILL {self.name} :{reason}"
                self.send([], data)

            self.exit(quitreason)
            data = f":{killed_by.id} KILL {self.id} :{reason}"
            IRCD.send_to_servers(killed_by, mtags=[], data=data)

        except Exception as ex:
            logging.exception(ex)

    def exit(self, reason: str) -> None:
        if self not in Client.table or self.exitted:
            # Already removed.
            self.close_socket()
            return
        if self in Client.table:
            Client.table.remove(self)
            logging.debug(f"Removed client {self.name} from client table. UID: {self.id}")
        self.exitted = 1
        if self.registered or 1:
            logging.debug(f"Exiting client {self.name}[{self.ip}]. Reason: {reason}")
        if self.server:
            if self == IRCD.current_link_sync:
                IRCD.current_link_sync = None
            self.server_exit(reason)
            logging.debug('-')
            logging.debug(f"Server successfully exitted. My current known UIDs (if any):")
            for client in IRCD.global_registered_clients():
                logging.debug(f"Client: {client.name} ({client.uplink.name}) -- UID: {client.id}")
            logging.debug('-')
        if self.user and self.registered:
            self.remove_user(reason)
        IRCD.global_client_count -= 1
        if self.local:
            IRCD.local_client_count -= 1
            IRCD.remove_delay_client(self)
            self.local.recvbuffer = []
            if reason and self.user:
                try:
                    self.local.socket.send(bytes(f"ERROR :Closing link: {self.name}[{self.user.realhost}] {reason}\r\n", "utf-8"))
                except Exception as ex:
                    pass

            self.close_socket()

        hook = Hook.LOCAL_QUIT if self.local else Hook.REMOTE_QUIT
        IRCD.run_hook(hook, self, reason)
        gc.collect()
        del self

    def close_socket(self):
        if not self.local:
            return
        if IRCD.use_poll and self.local.socket.fileno() > -1:
            try:
                IRCD.poller.unregister(self.local.socket)
            except KeyError:
                # Most likely already unregistered @ POLLNVAL event.
                pass
        if isinstance(self.local.socket, OpenSSL.SSL.Connection):
            try:
                self.local.socket.shutdown()
            except OpenSSL.SSL.Error:
                self.local.socket.close()
        else:
            try:
                self.local.socket.shutdown(socket.SHUT_WR)
            except:
                self.local.socket.close()

    def is_killed(self):
        return Flag.CLIENT_KILLED in self.flags

    def is_shunned(self):
        return Flag.CLIENT_SHUNNED in self.flags

    def add_flag(self, f: Flag):
        if f not in self.flags:
            self.flags.append(f)

    def add_swhois(self, line: str, remove_on_deoper: int = 0):
        Swhois.add_to_client(self, line, remove_on_deoper)

    def del_swhois(self, line: str):
        Swhois.remove_from_client(self, line)

    def add_md(self, name: str, value: str, sync: int = 1):
        ModData.add_to_client(self, name, value, sync)

    def del_md(self, name: str):
        ModData.remove_from_client(self, name)

    def get_md_value(self, name: str):
        if md := ModData.get_from_client(self, name):
            return md.value

    def flood_safe_on(self):
        flag = Flag.CLIENT_USER_FLOOD_SAFE
        if flag not in self.flags:
            self.flags.append(flag)

    def flood_safe_off(self):
        flag = Flag.CLIENT_USER_FLOOD_SAFE
        if flag in self.flags:
            self.flags.remove(flag)

    def is_flood_safe(self):
        return Flag.CLIENT_USER_FLOOD_SAFE in self.flags

    def check_flood(self):
        if self.is_flood_safe():
            self.local.sendq_buffer = []
            return
        if self.local and self.user:
            if not self.local.flood_penalty_time:
                self.local.flood_penalty_time = int(time())
            if self.class_:
                sendq = self.class_.sendq
                recvq = self.class_.recvq
            else:
                sendq, recvq = 65536, 65536

            real_buffer_str = '\r\n'.join([e[1] for e in self.local.backbuffer])
            real_sendq_str = '\r\n'.join([e[1] for e in self.local.sendq_buffer])
            buffer_len_recv = len(real_buffer_str)
            buffer_len_send = len(real_sendq_str)
            if buffer_len_recv >= recvq:
                flood_type = "recvq"
            else:
                flood_type = "sendq"
            if buffer_len_recv > recvq or buffer_len_send > sendq:
                flood_amount = buffer_len_recv if flood_type == "recvq" else buffer_len_send
                flood_limit = recvq if flood_type == "recvq" else sendq
                if self.registered:
                    IRCD.send_snomask(self, 'f',
                                      f"*** Flood -- {self.name} ({self.user.username}@{self.user.realhost})"
                                      f"has reached their max {'RecvQ' if flood_type == 'recvq' else 'SendQ'} ({flood_amount}) while the limit is {flood_limit}")
                self.exit("Excess Flood")
                return
            else:
                cmd_len = len(self.local.recvbuffer)
                max_cmds = recvq / 50
                max_cmds = int(max_cmds)
                if (cmd_len >= max_cmds) and (self.registered and int(time()) - self.creationtime >= 1):
                    if self.registered:
                        IRCD.send_snomask(self, 'f',
                                          f"*** Buffer Flood -- {self.name} ({self.user.username}@{self.user.realhost}) has reached "
                                          f"their max buffer length ({cmd_len}) while the limit is {max_cmds}")
                    self.exit("Excess Flood")
                    return

                if self.user:
                    flood_penalty_treshhold = 1_000_000 if 'o' not in self.user.modes else 10_000_000
                    if int(time()) - self.local.flood_penalty_time >= 60:
                        self.local.flood_penalty = 0
                        self.local.flood_penalty_time = 0
                    if self.local.flood_penalty >= flood_penalty_treshhold:
                        if self.registered:
                            IRCD.send_snomask(self, 'f',
                                              f"*** Flood -- {self.name} ({self.user.username}@{self.user.realhost}) has reached "
                                              f"their max flood penalty ({self.local.flood_penalty}) while the limit is {flood_penalty_treshhold}")
                        self.exit("Excess Flood")
                        return

    def assign_host(self):
        if not self.user:
            return
        if IRCD.get_setting("resolvehost"):
            try:
                realhost = gethostbyaddr(self.ip)[0]
                if realhost == "localhost" and not ipaddress.IPv4Address(self.ip).is_private:
                    # https://ipinfo.io/AS7552/27.71.152.0/21
                    # All those IP addresses seem to resolve to localhost.
                    raise Exception
                self.user.realhost = realhost
                IRCD.server_notice(self, f"*** Found your hostname: {self.user.realhost}")
            except:
                self.user.realhost = self.ip
                IRCD.server_notice(self, f"*** Couldn't resolve your hostname, using IP address instead")

        else:
            IRCD.server_notice(self, f"*** Host resolution disabled, using IP address instead")
            self.user.realhost = self.ip

        self.user.cloakhost = IRCD.get_cloak(self)

    def add_user_modes(self, modes):
        if not self.local:
            logging.error(f"Attempted to call add_user_modes() on non-local user: {self.name} {modes}")
            return
        for mode in list(modes):
            if not IRCD.get_usermode_by_flag(mode):
                logging.debug(f"[add_user_modes()] Could not find mode: {mode}")
                modes.remove(mode)
                continue

        filtered_modes = ''
        for mode in [m for m in modes if m not in self.user.modes]:
            filtered_modes += mode

        if filtered_modes:
            modes = ''.join(filtered_modes)
            self.user.modes += modes
            data = f":{self.name} MODE {self.name} +{modes}"
            self.send([], data)
            data = f":{self.id} MODE {self.name} +{modes}"
            IRCD.send_to_servers(self, [], data=data)

    def assign_class(self):
        """
        Assign class only after registration is complete.
        """
        clientmask_ip = f"{self.user.username}@{self.ip}"
        clientmask_host = f"{self.user.username}@{self.user.realhost}"
        for allow in IRCD.configuration.allow:
            allow_match = is_match(allow.mask, clientmask_host) or is_match(allow.mask, clientmask_ip)
            if allow_match:
                allow_class = allow
                if allow.password and self.local.authpass != allow.password:
                    logging.debug(f"Matching class '{allow_class}' requires a password, but password was invalid.")
                    logging.debug(f"Required: {allow.password}, received: {self.local.authpass}")
                    # Reject policy? Next class or kill client?:
                    if "reject-on-auth-fail" in allow.options:
                        logging.debug(f"Killing client: reject-on-auth-fail")
                        self.sendnumeric(Numeric.ERR_PASSWDMISMATCH)
                        self.exit("Invalid password")
                        return 0
                    logging.debug(f"Allow-block requires a password, but the correct password was not given.")
                    logging.debug("Trying next allow block...")
                    continue

                # Check if allow-block as options.
                if allow.options:
                    if "tls" in allow.options and not self.local.tls:
                        logging.debug(f"Allow-block requires TLS, client is plain. Trying next allow-block...")
                        continue

                # Check for "block" entries.
                if allow.block:
                    for entry in allow.block:
                        clientmask_ip = f"{self.user.username}@{self.local.ip}"
                        clientmask_host = f"{self.user.username}@{self.user.realhost}"
                        if is_match(entry, clientmask_ip) or is_match(entry, clientmask_host):
                            logging.info(f"Client {self} blocked by '{allow_class}': {entry}")
                            self.exit("Connection blocked by configuration policy")
                            return 0

                if not (class_match := IRCD.get_class_from_name(allow_class.class_obj)):
                    logging.debug(f"Client {self.name} has been rejected: no matching class found")
                    self.exit(f"You are not authorised to connect to this server")
                    return 0

                self.set_class_obj(class_match)

                self.local.allow = allow_class

                ip_count = len([c.local for c in IRCD.local_clients() if c.class_ and c.class_.name == allow.class_obj and c.ip == self.ip])
                class_count = len([c.local for c in Client.table if c.local and c.class_ == self.class_])

                if ip_count > allow.maxperip:
                    self.exit("Maximum connections from this IP reached.")
                    return 0

                if class_count > self.class_.max:
                    self.exit("Maximum connections for this class reached")
                    return 0
                break

        if not self.class_:
            self.exit(f"You are not authorised to connect to this server")
            return 0

        return 1

    def register_user(self):
        # Assign class here.
        if not self.assign_class():
            return

        """ Calling this in a thread so we can delay PRE_CONNECT hook without affecting other clients. """
        # Thread(target=welcome_user, args=(client,)).start()
        self.welcome_user()
        return

    def welcome_user(self):
        if self.registered:
            return
        logging.debug(f"New local user {self.name} UID: {self.id}")
        for result, hook_obj in Hook.call(Hook.PRE_CONNECT, args=(self,)):
            if result == Hook.DENY:
                logging.debug(f"Connection process denied for user {self.name} by module: {hook_obj}")
                self.exit("Connection closed by server")
                return

        if self.exitted:
            return

        if self.local.tls and hasattr(self.local.socket, "get_cipher_name"):
            if cipher_name := self.local.socket.get_cipher_name():
                cipher_version = self.local.socket.get_cipher_version()
                IRCD.server_notice(self, f"*** You are connected to {IRCD.me.name} with {cipher_version}-{cipher_name}")
                self.add_md("tls-cipher", f"{cipher_version}-{cipher_name}")

        self.sync(cause="welcome_user()")

        IRCD.local_user_count += 1
        if IRCD.local_user_count > IRCD.maxusers:
            IRCD.maxusers = IRCD.local_user_count

        IRCD.global_user_count += 1
        if IRCD.global_user_count > IRCD.maxgusers:
            IRCD.maxgusers = IRCD.global_user_count

        self.flood_safe_on()
        self.add_flag(Flag.CLIENT_REGISTERED)
        self.sendnumeric(Numeric.RPL_WELCOME, IRCD.me.name, self.name, self.user.username, self.user.realhost)
        self.sendnumeric(Numeric.RPL_YOURHOST, IRCD.me.name, IRCD.version)
        created_date = datetime.fromtimestamp(IRCD.boottime).strftime('%a %b %d %Y')
        created_time = datetime.fromtimestamp(IRCD.boottime).strftime('%H:%M:%S %Z')
        self.sendnumeric(Numeric.RPL_CREATED, created_date, created_time)
        self.sendnumeric(Numeric.RPL_MYINFO, IRCD.me.name, IRCD.version, IRCD.get_umodes_str(), IRCD.get_chmodes_str())
        Isupport.send_to_client(self)
        self.sendnumeric(Numeric.RPL_HOSTHIDDEN, self.user.cloakhost)

        msg = f"*** Client connecting: {self.name} ({self.user.username}@{self.user.realhost}) [{self.ip}] {self.get_ext_info()}"
        IRCD.log(self, "info", "connect", "LOCAL_USER_CONNECT", msg, sync=0)

        Command.do(self, "LUSERS")
        Command.do(self, "MOTD")

        # Give modes on connect.
        if conn_modes := IRCD.get_setting("modes-on-connect"):
            conn_modes = ''.join([m for m in conn_modes if m.isalpha() and m not in self.user.modes])
            modes = list(conn_modes)
            if self.local.tls:
                modes.append('z')
            modes = list(set(modes))
            if len(modes) > 0:
                self.add_user_modes(modes)

        IRCD.run_hook(Hook.LOCAL_CONNECT, self)
        self.flood_safe_off()

    def handle_recv(self):
        if Flag.CLIENT_HANDSHAKE_FINISHED not in self.flags:
            """
            First sockread.
            """
            self.flags.append(Flag.CLIENT_HANDSHAKE_FINISHED)
            IRCD.run_hook(Hook.NEW_CONNECTION, self)
            if not IRCD.is_except_client("throttle", self):
                throttle_treshhold, throttle_time = map(int, IRCD.get_setting("throttle").split(":"))
                total_conns = [c for c in IRCD.throttle if c.ip == self.ip and int(time()) - IRCD.throttle[c] <= throttle_time]
                if len(total_conns) >= throttle_treshhold:
                    self.exit("Throttling - You are (re)connecting too fast")
                    return
                IRCD.throttle[self] = int(time())

        if self.exitted:
            return

        self.local.last_msg_received = int(time())

        try:
            for line in list(self.local.recvbuffer):
                time_to_execute, recv = line
                if self.user:
                    if time_to_execute - time() > 0 and 'o' not in self.user.modes:
                        continue

                cmd = recv.split()[0].upper()
                # logging.warning(f"Msg from {self.name}: {recv}")
                if self.server and IRCD.current_link_sync and IRCD.current_link_sync != self and cmd != "SQUIT":
                    if self not in IRCD.process_after_eos:
                        IRCD.process_after_eos.append(self)
                        logging.debug(f"Currently in the middle of syncing to {IRCD.current_link_sync.name}, processing {self.name} recvbuffer after.")
                    continue

                if line in self.local.recvbuffer:
                    self.local.recvbuffer.remove(line)

                if not (recv := recv.strip()):
                    continue

                parsed_tags = []
                if recv[0] == '@':
                    tag_data = recv.split()[0][1:].split(';')
                    parsed_tags = IRCD.parse_remote_mtags(self, tag_data)
                    recv = ' '.join(recv.split()[1:])
                    if not recv.strip():
                        continue

                source_client = self
                find_source = recv.split()[0][1:]
                if recv[0] == ':':
                    if self.server:
                        if not IRCD.find_client(find_source) and self.server.authed:
                            logging.warning(f"Unknown server message from {find_source}: {recv}")
                            continue
                        # if not source_client:
                        #     source_client = self
                        recv = recv.split(' ', maxsplit=1)[1]
                        if not (source_client := IRCD.find_client(find_source)):
                            source_client = self
                        # logging.warning(f"Source client changed from {self.name} to {source_client.name}")
                        if self.server.authed:
                            """ Change source_client """
                            if not (source_client := IRCD.find_client(find_source)):
                                source_client = self
                        elif not (source_client := IRCD.find_user(find_source)):
                            source_client = self

                seen = []
                for tag in list(parsed_tags):
                    if tag.name in seen:
                        parsed_tags.remove(tag)
                        continue
                    seen.append(tag.name)

                if self.server:
                    source_client.mtags = parsed_tags

                source_client.recv_mtags = parsed_tags
                recv = recv.split(' ')
                for result, callback in Hook.call(Hook.PRE_COMMAND, args=(self, recv)):
                    if result == Hook.DENY:
                        logging.debug(f"PRE_COMMAND denied by {callback}")
                        logging.debug(f"Recv: {recv}")
                        return
                command = recv[0].upper()
                if (cmd := Command.find_command(source_client, command, *recv)) not in [0, 1]:
                    result, *args = cmd.check(source_client, recv)
                    if result != 0 and not self.server:
                        self.sendnumeric(result, *args)
                        continue
                    cmd.do(source_client, *recv)
                elif cmd == 0:
                    if not self.server:
                        self.sendnumeric(Numeric.ERR_UNKNOWNCOMMAND, command)
                        # Unknown command, but command still ended.
                        IRCD.run_hook(Hook.POST_COMMAND, self, recv[0], recv)
                        self.mtags = []
                        self.flood_safe_off()
                    continue
        except Exception as ex:
            logging.exception(ex)

    def send(self, mtags: list, data: str, call_hook=1):
        if type(data) != str:
            logging.error(f"Wrong data type @ send(): {data}")
            return
        data = data.strip()
        if not data or self.exitted \
                or self not in Client.table or not self.local \
                or not self.local.socket or (self.local.socket and self.local.socket.fileno() < 0):
            return
        if call_hook:
            data_list = data.split(' ')
            IRCD.run_hook(Hook.PACKET, IRCD.me, self.direction, self, data_list)
            data = ' '.join(data_list)
            if not data.strip():
                return

        if mtags := MessageTag.filter_tags(destination=self, mtags=mtags):
            data = f"@" + ';'.join([t.string for t in mtags]) + ' ' + data

        if IRCD.use_poll:
            # logging.debug(f"Setting {self.local.socket} flags to write mode")
            IRCD.poller.modify(self.local.socket, select.POLLOUT)
        self.local.sendbuffer += data + "\r\n"

        if self.user and 'o' not in self.user.modes:
            sendq_buffer_time = time()
            """ Keep the backbuffer entry duration based on the incoming data length. """
            delay = len(data) / 10
            sendq_buffer_time += delay
            self.local.sendq_buffer.append([sendq_buffer_time, data])
            self.check_flood()

    def direct_send(self, data):
        """ Directly sends data to a socket. """
        write_time = 0
        write_start = time()
        debug_out = 0
        try:
            self.local.socket.sendall(bytes(data, "utf-8"))
            self.local.bytes_sent += len(data)
            if debug_out:
                logging.debug(f"{self.name}[{self.ip}] < {data}")
            self.local.messages_sent += 1
            write_done = time()
            write_time = (write_done - write_start) * 1000
            if write_time >= 100:
                logging.debug(f"Writing to {self.name}[{self.ip}] took {write_time:.2f} millseconds seconds. Data: {data}")
        except Exception as ex:
            # logging.exception(ex)
            if write_time >= 100:
                logging.warning(f"Failed to write to {self.name}[{self.ip}] after {write_time} millseconds seconds. Data: {data}")
            self.exit(f"Write error: {str(ex)}")
            return


@dataclass(eq=False)
class LocalClient:
    allow: Allow = None
    authpass: str = ''
    socket: socket = None
    caps: list = field(default_factory=list)
    tls: OpenSSL = None
    error_str: str = ''
    nospoof: str = ''
    last_msg_received: int = 0
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
    backbuffer: [] = field(repr=False, default_factory=list)
    sendq_buffer: [] = field(repr=False, default_factory=list)
    auto_connect: int = 0
    handshake: int = 0


@dataclass(eq=False)
class User:
    account: str = '*'
    modes: str = ''
    operlogin: str = None  # The oper account as defined in confg.
    operclass: Operclass = None
    server: Server = None
    username: str = ''
    realhost: str = ''
    cloakhost: str = ''
    snomask: str = ''
    swhois: list = field(default_factory=list)  # Swhois dataclasses
    away: str = ''
    away_since: int = 0
    oper = None

    @property
    def channels(self):
        channels = []
        for channel in Channel.table:
            for member in channel.members:
                if member.client.user == self:
                    channels.append(channel)
                    break
        return channels


@dataclass(eq=False)
class Server:
    user = None
    mtags = []
    recv_mtags = []
    synced: int = 0
    authed: int = 0
    squit: int = 0
    link = None

    def flood_safe_off(self):
        pass

    def flood_safe_on(self):
        pass


@dataclass(eq=False)
class ChannelMember:
    client: Client = None
    modes: str = ''


@dataclass(eq=False)
class Command:
    table: ClassVar[list] = []
    trigger: str = ''
    parameters: int = 0
    flags: int = None
    func: Callable = None
    module: Module = None

    @staticmethod
    def add(module, func: Callable, trigger: str, params: int = 0, *flags: Flag):
        if not flags:
            flags = Flag.CMD_USER,
        cmd = Command()
        cmd.module = module
        cmd.func = func
        cmd.trigger = trigger
        cmd.flags = flags
        cmd.parameters = int(params)
        cmd.help = None
        Command.table.append(cmd)

    def cmd_flags_match(self, client):
        # flags_sum = sum(e.value for e in command.flags)
        """
        0 = UNKNOWN (not yet fully registered on the server, can be either client or a server.
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

    def check(self, client, recv):
        result, *args = self.cmd_flags_match(client)
        if result != 0:
            return result, *args
        # Don't count the actual command as a param.
        if (len(recv) - 1) < self.parameters:
            return Numeric.ERR_NEEDMOREPARAMS, self.trigger.upper()
        return 0,

    @staticmethod
    def find_command(client, trigger: str, *recv):
        for command in Command.table:
            if command.trigger.lower() == trigger.lower():
                return command

        for alias in IRCD.configuration.aliases:
            if alias.name.lower() == trigger.lower():
                if alias.target[0] in IRCD.CHANPREFIXES:
                    if not (target := IRCD.find_channel(alias.target)):
                        logging.debug(f"Alias target channel {alias.target} could not be found.")
                        continue
                else:
                    if alias.type == "services":
                        if not IRCD.find_server(IRCD.get_setting("services")):
                            client.sendnumeric(Numeric.ERR_SERVICESDOWN)
                            return 1

                    if not (target := IRCD.find_user(alias.target)):
                        logging.debug(f"Alias target user {alias.target} could not be found.")
                        return 1

                    if alias.type == "services" and target.uplink.name != IRCD.get_setting("services"):
                        return 1

                if target:
                    Command.do(client, "PRIVMSG", alias.target, *recv[1:])
                    return 1
        return 0

    @staticmethod
    def do(client: Client, *recv):
        trigger = recv[0]
        if cmd := Command.find_command(client, trigger):
            client.last_command = recv
            cmd.func(client, recv=list(recv))
            IRCD.run_hook(Hook.POST_COMMAND, client, trigger, recv)
            client.mtags = []
            client.flood_safe_off()


@dataclass(eq=False)
class Usermode:
    table: ClassVar[list] = []

    flag: str = ''
    is_global: int = 1
    unset_on_deoper: int = 0
    can_set: Callable = None
    module: Module = None
    desc: str = ''

    @staticmethod
    def allow_all(client):
        return 1

    @staticmethod
    def allow_opers(client):
        if client == IRCD.me or client.server:
            return 1
        return 1 if 'o' in client.user.modes else 0

    @staticmethod
    def allow_none(client):
        if client == IRCD.me or client.server:
            return 1
        return 0 if not client.server else 1

    @staticmethod
    def umodes_sorted_str():
        return ''.join(sorted([cmode.flag for cmode in Usermode.table]))

    def get_level_string(self):
        match self.can_set:
            case Usermode.allow_opers:
                return "IRCops only"
            case Usermode.allow_none:
                return "Settable by servers"
            case _:
                return None

    @staticmethod
    def add(module, flag: str, is_global: int, unset_on_deoper: int, can_set: callable, desc: str):
        if exists := next((um for um in Usermode.table if um.flag == flag), 0):
            logging.error(f"[{module.name}] Attempting to add user mode '{flag}' but it has already been added before by {exists.module.name}")
            return
        umode = Usermode()
        umode.flag = flag
        umode.is_global = is_global
        umode.unset_on_deoper = unset_on_deoper
        umode.can_set = can_set
        umode.module = module
        umode.desc = desc
        Usermode.table.append(umode)
        Isupport.add("USERMODES", Usermode.umodes_sorted_str(), server_isupport=1)

    @staticmethod
    def add_generic(flag: str):
        umode = Usermode()
        umode.module = None
        umode.flag = flag
        umode.can_set = Usermode.allow_none
        Usermode.table.append(umode)
        logging.debug(f"Adding generic support for missing user mode: {flag}")


@dataclass(eq=False)
class Channelmode:
    table: ClassVar[list] = []
    MEMBER: ClassVar[int] = 1
    LISTMODE: ClassVar[int] = 2
    CHK_PARAM: ClassVar[int] = 3
    CHK_ACCESS: ClassVar[int] = 4

    flag: str = ''
    prefix: str = ''
    rank: int = None
    type: int = 0
    level: int = 2
    sjoin_prefix: str = ''
    paramcount: int = 0
    unset_with_param: int = 0
    is_global: int = 1
    is_ok: Callable = None
    get_param: callable = lambda p: None
    module: Module = None
    desc: str = ''
    param_help: str = ''

    @staticmethod
    def add(module, cmode):
        if exists := next((cm for cm in Channelmode.table if cm.flag == cmode.flag), 0):
            logging.error(f"[{module.name}] Attempting to add user mode '{cmode.flag}' but it has already been added before by {exists.module.name}")
            return
        cmode.module = module
        Channelmode.table.append(cmode)
        Isupport.add("CHANMODES", IRCD.get_chmodes_str_categorized(), server_isupport=1)
        prefix_sorted = sorted([m for m in Channelmode.table if m.prefix and m.rank and m.type == Channelmode.MEMBER], key=lambda c: c.rank, reverse=True)
        if prefix_sorted:
            prefix_string = f"({''.join(cm.flag for cm in prefix_sorted)}){''.join(cm.prefix for cm in prefix_sorted)}"
            Isupport.add("PREFIX", prefix_string, server_isupport=1)

    @staticmethod
    def add_generic(flag: str, cat=4):
        cmode = Channelmode()
        cmode.module = None
        cmode.flag = flag
        cmode.is_ok = Channelmode.allow_none
        if cat in [2, 3]:
            cmode.paramcount = 1
            cmode.conv_param = lambda x: x
        if cat == 2:
            cmode.unset_with_param = 1

        Channelmode.table.append(cmode)
        logging.debug(f"Adding generic support for missing channel mode: {flag}")

    @staticmethod
    def allow_halfop(client, channel, *args):
        return channel.client_has_membermodes(client, "hoaq") or client.has_permission("channel:override:mode")

    @staticmethod
    def allow_chanop(client, channel, *args):
        return channel.client_has_membermodes(client, "oaq") or client.has_permission("channel:override:mode")

    @staticmethod
    def allow_chanadmin(client, channel, *args):
        return channel.client_has_membermodes(client, "aq") or client.has_permission("channel:override:mode")

    @staticmethod
    def allow_chanowner(client, channel, *args):
        return channel.client_has_membermodes(client, "q") or client.has_permission("channel:override:mode")

    @staticmethod
    def allow_opers(client, channel, *args):
        return 'o' in client.user.modes

    @staticmethod
    def allow_none(client, channel, *args):
        return client.server or not client.local

    def level_help_string(self):
        match self.is_ok:
            case Channelmode.allow_halfop:
                return "+h"
            case Channelmode.allow_chanop:
                return "+o"
            case Channelmode.allow_chanadmin:
                return "+a"
            case Channelmode.allow_chanowner:
                return "+q"
            case Channelmode.allow_opers:
                return "IRCops only"
            case Channelmode.allow_none:
                return "Settable by servers"

        level = ''.join([{2: '+h',
                          3: '+o',
                          4: '+a',
                          5: '+q',
                          6: 'IRCops only',
                          7: 'Settable by servers'}
                         [self.level]])
        return level


@dataclass(eq=False)
class Snomask:
    table: ClassVar[list] = []
    flag: str = ''
    is_global: int = 0
    module: Module = None

    @staticmethod
    def add(module, flag: str, is_global: int = 0, desc=''):
        if next((s for s in Snomask.table if s.flag == flag), 0):
            logging.error(f"Attempting to add duplicate snomask: {flag}")
            return
        snomask = Snomask()
        snomask.module = module
        snomask.flag = flag
        snomask.is_global = is_global
        snomask.desc = desc
        Snomask.table.append(snomask)


@dataclass(eq=False)
class Channel:
    # channel.membermodes.client
    table: ClassVar[list] = []
    name: str = ''
    # This list will hold ChannelMember objects.
    members: list = field(default_factory=list)
    invites: list = field(default_factory=list)
    modes: str = ''
    membercount: int = 0
    # List holding ChannelmodeParam objects.
    modeparams: list = field(default_factory=list)
    topic: str = ''
    topic_author: str = None
    topic_time: int = 0
    creationtime: int = 0
    List: dict = field(default_factory=dict)

    def init_lists(self):
        for mode in [m.flag for m in Channelmode.table if m.type == Channelmode.LISTMODE]:
            self.List[mode] = []

    def can_join(self, client: Client, key: str):
        """
        Return 0 if the client is allowed to join.
        """
        for invite in self.invites:
            if invite.to == client and invite.override:
                return 0

        if client.has_permission("channel:override:join"):
            return 0

        for result, callback in Hook.call(Hook.CAN_JOIN, args=(client, self, key)):
            if result != 0:
                return result
        return 0

    def user_can_see_member(self, user, target):
        """
        Check if `user` can see `target` on `channel`
        """
        for result, callback in Hook.call(Hook.VISIBLE_ON_CHANNEL, args=(user, target, self)):
            if result == Hook.DENY:
                return 0
        return 1

    def clients(self, client_cap=None, prefix=None) -> list:
        clients = []
        for client in [m.client for m in self.members]:
            if client_cap and not client.has_capability(client_cap):
                continue
            if prefix and prefix not in self.get_prefix_sorted_str(client) and 'o' not in client.user.modes:
                continue
            clients.append(client)
        return clients

    def get_clients_generator(self, client_cap=None, prefix=None):
        clients = (m.client for m in self.members
                   if (not client_cap or client_cap and m.client.has_capability(client_cap))
                   and (not prefix or prefix and (prefix in self.get_prefix_sorted_str(m.client) or 'o' in m.client.user.modes)))
        return clients

    def member_modes(self, client: Client):
        for member in self.members:
            if member.client == client:
                # User is on channel.
                return member.modes
        return ''

    def find_member(self, client):
        return next((m for m in self.members if m.client == client), 0)

    @staticmethod
    def get_membermodes_sorted() -> list:
        return sorted([cmode for cmode in Channelmode.table if cmode.type == cmode.MEMBER and cmode.prefix and cmode.rank], key=lambda c: c.rank, reverse=True)

    def get_modes_of_client_str(self, client: Client) -> str:
        modes = ''
        for cmode in [cmode for cmode in Channel.get_membermodes_sorted() if self.client_has_membermodes(client, cmode.flag)]:
            modes += cmode.flag
        return modes

    def get_prefix_sorted_str(self, client):
        prefix = ''
        for cmode in [cmode for cmode in Channel.get_membermodes_sorted() if self.client_has_membermodes(client, cmode.flag)]:
            prefix += cmode.prefix
        return prefix

    def get_sjoin_prefix_sorted_str(self, client):
        prefix = ''
        for cmode in [cmode for cmode in Channel.get_membermodes_sorted() if self.client_has_membermodes(client, cmode.flag)]:
            prefix += cmode.sjoin_prefix
        return prefix

    def client_has_membermodes(self, client, modes: str):
        if not (member := self.find_member(client)):
            return 0
        if set(member.modes).intersection(modes):
            return 1
        return 0

    def broadcast(self, client, data):
        IRCD.new_message(client)
        for member in [member for member in self.members if member.client.local]:
            if not client.uplink.server.synced:
                Batch.check_batch_event(mtags=client.mtags, started_by=client, target_client=member.client, event="netjoin")
            member.client.send(client.mtags, data)

    def create_member(self, client):
        if not self.find_member(client):
            member = ChannelMember()
            member.join_time = int(time())
            member.client = client
            self.members.append(member)
            return 1

    def member_give_modes(self, client: Client, mode: str):
        if not (member := self.find_member(client)):
            return
        member.modes += mode

    def member_take_modes(self, client: Client, modes: str):
        if not (member := self.find_member(client)):
            return
        for mode in modes:
            member.modes = member.modes.replace(mode, '')

    def add_param(self, mode, param):
        """ If it already exists, it will update it. """
        if pm := next((p for p in self.modeparams if p.mode == mode), 0):
            pm.param = param
            return
        pm = ChannelmodeParam()
        pm.mode = mode
        pm.param = param
        self.modeparams.append(pm)

    def del_param(self, mode: str):
        if pm := next((p for p in self.modeparams if p.mode == mode), 0):
            self.modeparams.remove(pm)

    def get_param(self, mode: str):
        return next((p.param for p in self.modeparams if p.mode == mode), 0)

    def add_invite(self, to: Client, by: Client, override: int = 0):
        if not (inv := self.get_invite(to)):
            inv = Invite()
        else:
            self.invites.remove(inv)
        inv.to = to  # Client being invited.
        inv.by = by  # Client making the invite.
        inv.override = override  # If the user has been invite by an IRCOps or a chanops or higher, it can override most channelmodes.
        inv.when = int(time())
        self.invites.append(inv)

    def del_invite(self, invite):
        if invite in self.invites:
            self.invites.remove(invite)

    def get_invite(self, to: Client):
        return next((inv for inv in self.invites if inv.to == to), 0)

    def mask_in_list(self, mask, _list):
        for entry in _list:
            if mask == entry.mask:
                return 1
        return 0

    def check_match(self, client, match_type, mask=None):
        if match_type not in self.List:
            return 0
        for b in self.List[match_type]:
            check_mask = b.mask if not mask else mask
            if IRCD.client_match_mask(client, check_mask):
                return 1

            for extban in Extban.table:
                if len(check_mask.split(':')) < 2:
                    continue
                try:
                    if extban.is_match(client, self, check_mask):
                        return 1
                except Exception as ex:
                    logging.exception(ex)
                    return 0
        return 0

    def is_banned(self, client, mask=None):
        if client.has_permission("channel:override:join:ban"):
            return 0
        for invite in self.invites:
            if invite.to == client and invite.override:
                return 0
        if self.check_match(client, 'b', mask):
            return 1

    def is_exempt(self, client):
        if self.check_match(client, 'e'):
            return 1

    def is_invex(self, client):
        if self.check_match(client, 'I'):
            return 1

    def level(self, client):
        if client.server or client.ulined:
            return 1000
        umode_levels = {"q": 5, "a": 4, "o": 3, "h": 2, "v": 1}
        for m in umode_levels:
            if self.client_has_membermodes(client, m):
                return umode_levels[m]
        return 0

    def add_to_list(self, client, mask, _list, setter=None, timestamp=None):
        if next((e for e in _list if mask == e.mask), 0):
            return 0
        if not setter:
            setter = client.name
        if not timestamp:
            timestamp = int(time())
        ban = ListEntry(mask=mask, set_by=setter, set_time=int(timestamp))
        _list.append(ban)
        return 1

    def remove_from_list(self, mask, _list):
        masks = [mask] if type(mask) != list else mask
        for mask in list(masks):
            if entry := next((e for e in _list if mask == e.mask), None):
                # entry = self.find_entry(mask, _list)
                # if entry:
                _list.remove(entry)
                return entry.mask

    def remove_client(self, client: Client):
        self.membercount -= 1
        if member := self.find_member(client):
            self.members.remove(member)
        else:
            logging.debug(f"Unable to remove {client.name} (uplink={client.uplink.name}) from channel {self.name}: member not found")

        if self.membercount == 0:
            IRCD.destroy_channel(IRCD.me, self)

    def do_part(self, client: Client, reason: str = ''):
        reason = reason[:128]
        data = f":{client.fullmask} PART {self.name}{' :' + reason if reason else ''}"
        for member in [m for m in self.members if m.client.local]:
            if not self.user_can_see_member(member.client, client):
                continue
            member.client.send(client.mtags, data)

        if self.name[0] != '&':  # and (client.local or (client.server and client.server.synced)):
            data = f":{client.id} PART {self.name}{' :' + reason if reason else ''}"
            IRCD.send_to_servers(client, client.mtags, data)
        self.remove_client(client)

    def do_join(self, mtags, client: Client):
        self.membercount += 1
        if not self.find_member(client):
            self.create_member(client)

        if invite := self.get_invite(client):
            self.del_invite(invite)

        join_message = f":{client.fullmask} JOIN {self.name}"
        for member in [m for m in self.members if m.client.local]:
            if not self.user_can_see_member(member.client, client):
                continue
            if not client.uplink.server.synced:
                Batch.check_batch_event(mtags=mtags, started_by=client.uplink, target_client=member.client, event="netjoin")
            data = join_message
            if member.client.has_capability("extended-join"):
                data += f" {client.user.account} :{client.info}"
            member.client.send(mtags, data)

        if len(self.members) == 1 and client.local:
            if self.name[0] != '+' and "P" not in self.modes:
                self.member_give_modes(client, 'o')
                if modes_on_join := IRCD.get_setting("modes-on-join"):
                    Command.do(IRCD.me, "MODE", self.name, *modes_on_join.split(), str(self.creationtime))

        if self.name[0] != '&':
            prefix = self.get_sjoin_prefix_sorted_str(client)
            # data = f":{client.id} JOIN {self.name}"
            # data = f":{IRCD.me.id} SJOIN {self.creationtime} {self.name} :{prefix}{client.id}"
            data = f":{client.uplink.id} SJOIN {self.creationtime} {self.name} :{prefix}{client.id}"
            IRCD.send_to_servers(client, client.mtags, data)


@dataclass
class ChannelmodeParam:
    mode: str = ''
    param: str = ''


@dataclass(eq=False)
class Swhois:
    priority: int = 0
    line: str = ''
    remove_on_deoper: int = 0

    @staticmethod
    def add_to_client(client: Client, line: str, remove_on_deoper=0):
        if next((sw for sw in client.user.swhois if sw.line == line), 0):
            return
        swhois = Swhois(line=line)
        swhois.remove_on_deoper = remove_on_deoper
        client.user.swhois.append(swhois)
        data = f":{IRCD.me.id} SWHOIS + {client.id} :{swhois.line}"
        IRCD.send_to_servers(client, [], data)

    @staticmethod
    def remove_from_client(client: Client, line: str):
        if not (swhois := next((swhois for swhois in client.user.swhois if swhois.line == line), 0)):
            return
        client.user.swhois.remove(swhois)
        data = f":{IRCD.me.id} SWHOIS - {client.id} :{swhois.line}"
        IRCD.send_to_servers(client, [], data)


@dataclass
class Invite:
    table: ClassVar[list] = []
    by: Client = None
    to: Client = None
    when: int = 0


class Configuration:
    def __init__(self):
        self.entries = []

        # Information from settings { } blocks.
        self.settings = {}

        self.modules = []
        self.opers = []
        self.operclasses = []
        self.listen = []
        # List holding our ports, to skip is_port_in_use() check inside config_test_listen().
        self.our_ports = []
        self.vhost = []
        self.allow = []
        self.spamfilters = []
        self.excepts = []
        self.connectclass = []
        self.links = []
        self.aliases = []

        self.conf_file = ''

    @staticmethod
    def get_blocks(blockname):
        return [b for b in IRCD.configuration.entries if b.name == blockname]

    @staticmethod
    def get_block(blockname):
        return next((b for b in IRCD.configuration.entries if b.name == blockname), 0)

    @staticmethod
    def get_items(path: str):
        path_split = path.split(':')
        if len(path_split) < 2:
            return
        block_name = path_split[0]
        block_path = path_split[1:]
        for block in IRCD.configuration.get_blocks(block_name):
            if items := block.get_items(':'.join(block_path)):
                return items

    @staticmethod
    def setting_empty(key):
        if key not in IRCD.configuration.settings:
            return 1
        return 0

    @staticmethod
    def get_oper(name):
        return next((o for o in IRCD.configuration.opers if o.name == name), 0)

    @staticmethod
    def get_class(name: str):
        return next((c for c in IRCD.configuration.connectclass if c.name == name), 0)

    @staticmethod
    def get_module_by_package(package):
        for m in IRCD.configuration.modules:
            if package == m.name:
                return True
        return next((m for m in IRCD.configuration.modules if m.name == package), 0)

    @staticmethod
    def get_listen_by_port(port):
        if not port.isdigit():
            return 0
        return next((listen for listen in IRCD.configuration.listen if int(listen.port) == int(port)), 0)


@dataclass(eq=False)
class IRCD:
    me: None
    configuration: Configuration = Configuration()  # Final configuration class.
    build_conf: Configuration = Configuration()  # Configuration class.
    # configuration: None
    hostinfo: str = ''
    conf_path: str = ''
    conf_file: str = ''
    isupport: ClassVar[list] = []  # Isupport classes
    throttle: ClassVar[dict] = {}
    maxusers: int = 0
    maxgusers: int = 0
    local_user_count: int = 0
    global_user_count: int = 0
    local_client_count: int = 0
    global_client_count: int = 0
    channels: int = 0
    channel_count: int = 0
    rehashing: int = 0
    default_tlsctx = None
    current_link_sync: Client = None
    process_after_eos: ClassVar[list] = []
    send_after_eos: ClassVar[dict] = {}
    delayed_connections: ClassVar[list] = []
    versionnumber: str = '3.0'
    version: str = f'ProvisionIRCd-{versionnumber}-beta'
    forked: int = 1
    use_poll: int = 1
    boottime: int = 0
    running: int = 0
    poller = None
    last_activity: int = 0
    uid_iter = None

    NICKLEN: int = 0
    NICKCHARS: str = "abcdefghijklmnopqrstuvwxyz0123456789`^-_[]{}|\\"
    CHANPREFIXES = "#+&"
    CHANLEN = 32
    CHANCHARS = "abcdefghijklmnopqrstuvwxyz0123456789`#$^*()-=_[]{}|;':\"<>"
    HOSTCHARS = "abcdefghijklmnopqrstuvwxyz0123456789.-"

    @staticmethod
    def boot(fork=1):
        IRCD.me.server = IRCD.me
        IRCD.me.direction = IRCD.me
        IRCD.me.uplink = IRCD.me
        if not fork:
            IRCD.forked = 0
        IRCD.running = 1
        IRCD.boottime = int(time())
        v = version.split('\\n')[0].strip()
        IRCD.hostinfo = f"Python {v}"
        Isupport.add("NETWORK", IRCD.me.info.replace(" ", "-"))
        if fork and os.name == "posix":
            pid = os.fork()
            if pid:
                logging.info(f'PID [{pid}] forking to the background')
                IRCDLogger.fork()
                exit()

    @staticmethod
    def log(client, level: str, rootevent: str, event: str, message: str, sync: int = 1):
        pass

    @staticmethod
    def get_setting(key):
        if key in IRCD.configuration.settings:
            return IRCD.configuration.settings[key]

    @staticmethod
    def set_setting(key, value):
        IRCD.configuration.settings[key] = value

    @staticmethod
    def set_setting_list(key, value):
        if key not in IRCD.configuration.settings:
            IRCD.configuration.settings[key] = []
        if value in IRCD.configuration.settings[key]:
            IRCD.configuration.settings[key].remove(value)
        IRCD.configuration.settings[key].append(value)

    @staticmethod
    def is_except_client(what, client):
        """
        :param what:        What to check for. Examples are: gline, shun, dnsbl.
                            If what == 'ban', it will collectively check for all of the following:
                            kline, gline, zline, gzline, shun, spamfilter, dnsbl
        """
        if not client.user:
            return 1
        what = what.lower()

        """ Check /eline matches """
        for tkl in [tkl for tkl in Tkl.table if tkl.type == "E"]:
            if what == "ban" and not [t for t in tkl.bantypes if t in "kGzZsFd"]:
                continue
            if not (tkl_what := Tkl.get_flag_of_what(what)):
                continue
            if tkl_what.flag not in tkl.bantypes:
                continue
            if what == "dnsbl" and 'd' not in tkl.bantypes:
                continue
            if what == "spamfilter" and 'F' not in tkl.bantypes:
                continue
            if tkl.ident == "~certfp:":
                if (fp := client.get_md_value("certfp")) and fp == tkl.host:
                    return 1
            if tkl.ident == "~account:":
                if client.user.account != '*':
                    if tkl.host == '*' and client.user.account != '*':
                        return 1
                    if is_match(tkl.host, client.user.account):
                        return 1

            ident = client.user.username
            if not ident:
                ident = '*'
            for mask in [f"{ident}@{client.user.realhost}", f"{ident}@{client.ip}", client.ip]:
                if is_match(tkl.mask, mask):
                    return 1

        for e in IRCD.configuration.excepts:
            """
            If the exception does not have 'ban' name,
            explicitly check for exceptions matching that name.
            """
            if e.name != "ban" and what != e.name:
                continue
            if not e.types and what != e.name:
                continue
            if e.types and what not in e.types:
                """
                Checks against exceptions.conf "ban { types { ... } }" block.
                """
                continue

            if (fp := client.get_md_value("certfp")) and fp in e.certfp_mask:
                return 1
            if client.user.account != '*':
                for account in e.account_mask:
                    if account == '*' and client.user.account != '*':
                        return 1
                    if is_match(account, client.user.account):
                        return 1
            for ip in e.ip_mask:
                if is_match(ip, client.ip):
                    return 1
            for e_mask in e.mask:
                ident = client.user.username
                if not ident:
                    ident = '*'
                for mask in [f"{ident}@{client.user.realhost}", f"{ident}@{client.ip}", client.ip]:
                    if len(e_mask) == 1 and is_match(e_mask[0], mask):
                        return 1
        return 0

    @staticmethod
    def write_data_file(json_dict: dict, filename: str):
        if not os.path.exists("data"):
            os.mkdir("data")
        with open(f"data/{filename}", "w+") as f:
            json_out = json.dumps(json_dict, indent=4)
            f.write(json_out)

    @staticmethod
    def read_data_file(filename: str) -> dict:
        data = {}
        if not os.path.exists("data"):
            os.mkdir("data")
        if not os.path.exists(f"data/{filename}"):
            return data
        with open(f"data/{filename}") as f:
            try:
                data = json.load(f)
            except json.decoder.JSONDecodeError:
                data = {}
        return data

    @staticmethod
    def delay_client(client: Client, delay: int | float, label: str):
        """
        Delay a client for maximum <delay> seconds.
        If the process that called this method ends earlier,
        the delay will be removed before <delay>.
        """
        if not client.local or not client.user:
            return
        # logging.debug(f"Delaying client {client.name} for {delay} seconds. Label: {label}")
        expire = time() + delay
        if d := next((d for d in IRCD.delayed_connections if d[0] == client and d[2] == label), 0):
            if d[1] > expire:
                """
                Client is already being delayed with a longer delay than given,
                so keeping that one instead.
                """
                return
        IRCD.delayed_connections.append((client, expire, label))

    @staticmethod
    def remove_delay_client(client, label=None):
        if not client.local or not client.user:
            return
        # logging.debug(f"Removing delay of client {client.name}. Label: {label}")
        for entry in list(IRCD.delayed_connections):
            c, expire, c_label = entry
            if c == client:
                if label and c_label == label or not label:
                    IRCD.delayed_connections.remove(entry)

        if not next((d for d in IRCD.delayed_connections if d[0] == client), 0):
            if client.handshake_finished():
                client.register_user()

    @staticmethod
    def is_valid_channelname(name: str) -> int:
        if name[0] not in IRCD.CHANPREFIXES:
            return 0

        for char in name[1:]:
            if char.lower() not in IRCD.CHANCHARS:
                return 0

        return 1

    @staticmethod
    def strip_format(string: str) -> str:
        """
        Strips all colors, bold, underlines, italics etc. from a string, and then returns it.
        """

        regex = re.compile(r"\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)
        stripped = regex.sub('', string).strip()
        return stripped

    @staticmethod
    def parse_remote_mtags(self, remote_mtags) -> list:
        """
        Received remote tag: msgid=43c8a33695c511edbaaa
        Received remote tag: dev.provisionweb.org/oper=admin
        Received remote tag: time=2023-01-16T17:43:19.400Z

        Add these tags to outgoing messages to local users.
        """

        mtags = []

        for tag in remote_mtags:
            value = None
            name = tag
            if '=' in tag:
                name, value = tag.split('=')
            if tag_obj := MessageTag.find_tag(name):
                if tag_obj.local and (self.server or not self.local):
                    logging.warning(f"Received local tag {tag_obj} from server {self.name} -- skipping")
                    continue
                new_tag = tag_obj(value=value)
                # Keep original name, such as originating server name in oper-tag.
                new_tag.name = name
                mtags.append(new_tag)
            elif name.startswith('+') and not tag_obj:
                logging.debug(f"Received non-existent client-tag from {self.name}: {tag}")
        return mtags

    @staticmethod
    def do_delayed_process():
        IRCD.current_link_sync = None
        for server_client in list(IRCD.process_after_eos):
            logging.debug(f"Processing delayed recvbuffer of: {server_client.name}")
            server_client.handle_recv()
            if server_client in IRCD.process_after_eos:
                IRCD.process_after_eos.remove(server_client)

    @staticmethod
    def client_match_mask(client, mask):
        if is_match(mask, f'{client.name}!{client.user.username}@{client.user.realhost}'):
            return 1
        if is_match(mask, f'{client.name}!{client.user.username}@{client.ip}'):
            return 1
        if is_match(mask, f'{client.name}!{client.user.username}@{client.user.cloakhost}'):
            return 1
        return 0

    @staticmethod
    def port_in_use(port: int):
        return next((ls for ls in IRCD.configuration.listen if ls.port == port and ls.listening), 0)

    @staticmethod
    def run_parallel_function(target, args=()):
        """ Run a threaded function once. Does not return anything. """
        t = Thread(target=target, args=args)
        t.daemon = 1
        t.start()

    @staticmethod
    def get_first_available_uid(client):
        # The reason I'm still using this UID method instead of the superior one below,
        # is because I want to fix an issue where ghost UIDs are still present somewhere, for some reason.
        # I would first like to find out why that is.
        """ 456,976 possibilities. """
        uid_iter = itertools.product(string.ascii_uppercase, repeat=4)
        for i in uid_iter:
            uid = IRCD.me.id + ''.join(i)
            if not IRCD.find_user(uid):
                return uid
        client.exit(f"UID exhaustion")
        logging.warning(f"No more available UIDs! This should never happen unless you have over 456,976 local users.")

    @staticmethod
    def initialise_uid_generator():
        while 1:
            yield from (IRCD.me.id + ''.join(i) for i in itertools.product(string.ascii_uppercase, repeat=6))

    @staticmethod
    def get_next_uid(client):
        if not IRCD.uid_iter:
            IRCD.uid_iter = IRCD.initialise_uid_generator()
        while (uid := next(IRCD.uid_iter)) and IRCD.find_user(uid):
            pass
        return uid

    @staticmethod
    def get_random_interval():
        interval = 60
        if hasattr(IRCD.me, "id"):
            for char in IRCD.me.id:
                if char.isdigit():
                    interval += int(char)
        interval += randrange(1800)
        return interval

    @staticmethod
    def get_cloak(client, host=None):
        """
        host = received hostname, depending on resolve settings.
        Can either be IP or realhost.
        """
        if not host:
            host = client.user.realhost
            ip = client.ip
        else:
            ip = host

        if "static" in host or '.ip-' in host:
            host = ip

        cloak_key = IRCD.get_setting("cloak-key")
        key = f'{host}{cloak_key}'
        hashhost = hashlib.sha512(bytes(key, "utf-8"))
        hex_dig = hashhost.hexdigest()
        cloak1 = hex(binascii.crc32(bytes(hex_dig[0:32], "utf-8")) % (1 << 32))[2:]
        cloak2 = hex(binascii.crc32(bytes(hex_dig[32:64], "utf-8")) % (1 << 32))[2:]

        if host.replace('.', '').isdigit():
            cloak3 = hex(binascii.crc32(bytes(hex_dig[64:96], "utf-8")) % (1 << 32))[2:]

            cloakhost = cloak1 + '.' + cloak2 + '.' + cloak3 + '.IP'
            return cloakhost
        c = 0
        for part in host.split('.'):
            c += 1
            if part.replace('-', '').isalpha():
                break
        if c == 1:
            c += 1
        host = '.'.join(host.split('.')[c - 1:])

        prefix = ''
        if IRCD.get_setting("cloak-prefix"):
            prefix = IRCD.get_setting("cloak-prefix") + '-'

        cloakhost = prefix + cloak1 + '.' + cloak2 + '.' + host
        cloakhost = cloakhost.removesuffix(".")
        return cloakhost

    @staticmethod
    def get_member_prefix_str_sorted():
        prefix_sorted = sorted([m for m in Channelmode.table if m.prefix and m.rank and m.type == Channelmode.MEMBER], key=lambda c: c.rank, reverse=True)
        return ''.join([m.prefix for m in prefix_sorted])

    @staticmethod
    def get_time_string():
        utc_time = datetime.utcnow().timestamp()
        time_string = f"{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')}.{round(utc_time % 1000)}Z"
        return time_string

    @staticmethod
    def get_allow(client):
        # Assign a class to client based on allow-block.
        for allow in IRCD.configuration.allow:
            clientmask_ip = f'{client.user.username}@{client.ip}'
            clientmask_hostname = f'{client.user.username}@{client.hostname}'
            allow_match = is_match(allow.mask, clientmask_ip) or is_match(allow.mask, clientmask_hostname)
            if allow_match:
                return allow

    @staticmethod
    def get_class_from_name(name: str):
        return next((cls for cls in IRCD.configuration.connectclass if cls.name == name), 0)

    @staticmethod
    def module_by_header_name(name: str):
        return next((m for m in IRCD.configuration.modules if m.header.get("name") == name), 0)

    @staticmethod
    def get_usermode_by_flag(flag: str):
        return next((umode for umode in Usermode.table if umode.flag == flag), 0)

    @staticmethod
    def get_parammodes_str() -> str:
        return ''.join([cmode.flag for cmode in Channelmode.table if cmode.paramcount])

    @staticmethod
    def get_list_modes_str() -> str:
        return ''.join([cmode.flag for cmode in Channelmode.table if cmode.type == Channelmode.LISTMODE])

    @staticmethod
    def get_umodes_str():
        return ''.join(sorted([m.flag for m in Usermode.table]))

    @staticmethod
    def get_chmodes_str():
        return ''.join(sorted([m.flag for m in Channelmode.table]))

    @staticmethod
    def get_chmodes_str_categorized():
        one, two, three, four = [], [], [], []
        for mode in Channelmode.table:
            if mode.type == Channelmode.MEMBER:
                continue
            if mode.type == Channelmode.LISTMODE:
                one.append(mode.flag)
            elif mode.unset_with_param:
                # Modes that require param on set and unset.
                two.append(mode.flag)
                continue
            elif mode.paramcount and not mode.unset_with_param:
                three.append(mode.flag)
                continue
            elif not mode.paramcount:
                four.append(mode.flag)
        result = f"{''.join(one)},{''.join(two)},{''.join(three)},{''.join(four)}"
        return result

    @staticmethod
    def channel_modes():
        return Channelmode.table

    @staticmethod
    def get_channelmode_by_flag(flag: str):
        return next((m for m in Channelmode.table if m.flag == flag), 0)

    @staticmethod
    def remote_clients():
        return [c for c in Client.table if not c.local]

    @staticmethod
    def local_clients():
        return [c for c in Client.table if c.local]

    @staticmethod
    def global_clients():
        return Client.table

    @staticmethod
    def global_registered_clients():
        return [c for c in Client.table if c.registered]

    @staticmethod
    def local_users():
        return [c for c in Client.table if c.local and c.user]

    @staticmethod
    def global_users():
        return [c for c in Client.table if c.user]

    @staticmethod
    def global_registered_users():
        return [c for c in Client.table if c.user and c.registered]

    @staticmethod
    def local_servers():
        return [c for c in Client.table if c.local and c.server]

    @staticmethod
    def global_servers():
        return [c for c in Client.table if c.server]

    @staticmethod
    def get_channels():
        return Channel.table

    @staticmethod
    def unregistered_clients() -> list:
        return [c for c in Client.table if not c.registered and c.local]

    @staticmethod
    def find_user(find: str):
        if not find:
            return
        find = find.removeprefix(':')
        for client in [c for c in Client.table if c.user and c.id]:
            if find.lower() in [client.name.lower(), client.id.lower()]:
                return client

    @staticmethod
    def find_channel(name: str):
        if not name:
            return
        for channel in Channel.table:
            if channel.name.lower() == name.lower():
                return channel

    @staticmethod
    def common_channels(p1, p2):
        """ Return common channels between p1 and p2 """
        if type(p1) == str:
            p1 = IRCD.find_user(p1)
        if type(p2) == str:
            p2 = IRCD.find_user(p2)
        return next((c for c in IRCD.get_channels() if c.find_member(p1) and c.find_member(p2)), 0)

    @staticmethod
    def create_channel(client, name: str):
        channel = Channel()
        channel.name = name
        channel.creationtime = int(time())
        channel.init_lists()
        Channel.table.append(channel)
        IRCD.channel_count += 1
        IRCD.run_hook(Hook.CHANNEL_CREATE, client, channel)
        return channel

    @staticmethod
    def destroy_channel(client, channel):
        Channel.table.remove(channel)
        IRCD.channel_count -= 1
        IRCD.run_hook(Hook.CHANNEL_DESTROY, client, channel)

    @staticmethod
    def find_server(find: str):
        """ Find a server based on ID/name """
        if not find:
            return
        find = find.removeprefix(':')
        if hasattr(IRCD, "me"):
            if find.lower() in [IRCD.me.name.lower(), IRCD.me.id.lower()]:
                return IRCD.me
        for client in Client.table:
            if not client.server or not client.id:
                continue
            if find.lower() in [client.name.lower(), client.id.lower()]:
                return client

    @staticmethod
    def find_client(find: str):
        if not find:
            return
        """ Find a client based on ID/name """
        find = find.removeprefix(':')
        if hasattr(IRCD, "me"):
            if find.lower() in [IRCD.me.name.lower(), IRCD.me.id.lower()]:
                return IRCD.me
        for client in Client.table:
            if not client.id:
                continue
            if find.lower() in [client.name.lower(), client.id.lower()]:
                return client

    @staticmethod
    def find_server_match(find: str) -> list:
        """ Support for wildcards. """
        if not find:
            return []
        find = find.removeprefix(':')
        matches = []
        if is_match(find.lower(), IRCD.me.name.lower()) or is_match(find.lower(), IRCD.me.id.lower()):
            matches.append(IRCD.me)
        for client in Client.table:
            if not client.server or not client.id:
                continue
            if is_match(find.lower(), client.name.lower()) or is_match(find.lower(), client.id.lower()):
                matches.append(client)
        return matches

    @staticmethod
    def find_remote_server(find: str):
        if not find:
            return
        find = find.removeprefix(':')
        for client in Client.table:
            if not client.server or not client.id or not client.registered:
                continue
            if find.lower() in [client.name.lower(), client.id.lower()]:
                return client

    @staticmethod
    def run_hook(hook, *args) -> None:
        for _, _ in Hook.call(hook, args=args):
            pass

    @staticmethod
    def new_message(client):
        IRCD.run_hook(Hook.NEW_MESSAGE, client)
        # Filter duplicate tags from self.sender.mtags, keeping only first.
        filtered_tags = []
        for tag in client.mtags:
            if tag.name not in [t.name for t in filtered_tags]:
                filtered_tags.append(tag)
        client.mtags = filtered_tags

    @staticmethod
    def send_to_one_server(client: Client, mtags: list, data: str):
        """
        Send a message to a single server in a straight line
        skipping irrelevant servers.
        """
        destination = client if client.local else client.direction
        destination.send(mtags, data)

    @staticmethod
    def send_to_servers(client: Client, mtags: list, data: str):
        """
        :param client:      The server from where this message is coming from.
        """
        for to_client in [to_client for to_client in Client.table if to_client.server and to_client.local]:  # and to_client.server.synced]:
            if client and client != IRCD.me and to_client == client.direction:
                continue
            # logging.debug(f"Syncing from {client.name} to {to_client.name}: {data}")
            # logging.debug(f"Client direction: {client.direction.name}")
            if IRCD.current_link_sync == to_client:
                """ Destination server is not done syncing. """
                logging.warning(f"[send_to_servers()] Trying to sync data to server {to_client.name} but we're still syncing. Sending after we receive their EOS.")
                logging.warning(f"This data is: {data.rstrip()}")
                if to_client not in IRCD.send_after_eos:
                    IRCD.send_after_eos[to_client] = []
                delayed_data = (mtags, data)
                IRCD.send_after_eos[to_client].append(delayed_data)
                return
            to_client.send(mtags, data)

    @staticmethod
    def send_to_local_common_chans(client, mtags, client_cap=None, data=''):
        broadcast = []
        for b_client in [c for c in IRCD.local_clients() if c != client]:
            if b_client in broadcast:
                continue
            for channel in IRCD.get_channels():
                if (channel.find_member(client) or client == IRCD.me) and channel.find_member(b_client):
                    # Now check if user can see sender.
                    if client.user and not channel.user_can_see_member(b_client, client):
                        continue
                    if client_cap and not b_client.has_capability(client_cap):
                        continue
                    b_client.send(mtags, data)
                    broadcast.append(b_client)
                    break

    @staticmethod
    def get_snomask(flag: str):
        return next((sn for sn in Snomask.table if sn.flag == flag), 0)

    @staticmethod
    def send_snomask(client: Client, flag: str, data: str):
        if not (snomask := IRCD.get_snomask(flag)):
            return
        data = data.removeprefix(':')
        source = client if client == IRCD.me or client.server else client.uplink
        for c in [c for c in Client.table if c.user and c.local and 's' in c.user.modes and snomask.flag in c.user.snomask]:
            Batch.check_batch_event(mtags=c.mtags, started_by=source, target_client=c, event="netjoin")
            local_data = f":{source.name} NOTICE {c.name} :{data}"
            c.send([], local_data)
        if snomask.is_global:
            out_data = f":{source.id} SENDSNO {flag} :{data}"
            IRCD.send_to_servers(client, [], out_data)

    @staticmethod
    def server_notice(client: Client, data: str):  # server: Client):
        # if server:
        #     server = server
        # else:
        #     server = client.uplink

        # server.name
        data = f":{client.uplink.name} NOTICE {client.name} :{data}"
        client.send([], data)


@dataclass(eq=False)
class Isupport:
    table: ClassVar[list] = []
    name: str = ''
    value: str = ''
    server: int = 0

    @property
    def string(self):
        return f'{self.name}{f"={self.value}" if self.value else ""}'

    @staticmethod
    def add(name: str, value=None, server_isupport=0):
        if (isupport := Isupport.get(name)) and value:
            isupport.value = value
            return
        isupport = Isupport()
        isupport.name = name
        isupport.value = value
        Isupport.server = server_isupport
        Isupport.table.append(isupport)

    @staticmethod
    def targmax(cmdname: str, value=''):
        if type(value) == int:
            value = str(value)
        if isupport := Isupport.get("TARGMAX"):
            isupport.value += f",{cmdname}:{value}"
            return
        Isupport.add(name="TARGMAX", value=f"{cmdname}:{value}")

    @staticmethod
    def get(name):
        return next((isupport for isupport in Isupport.table if isupport.name.lower() == name.lower()), 0)

    @staticmethod
    def send_to_client(client):
        line = []
        for isupport in Isupport.table:
            line.append(isupport.string)
            if len(line) == 15:
                client.sendnumeric(Numeric.RPL_ISUPPORT, ' '.join(line))
                line = []
                continue
        client.sendnumeric(Numeric.RPL_ISUPPORT, ' '.join(line))


@dataclass(eq=False)
class MessageTag:
    table: ClassVar[list] = []

    name: str = ''
    value: str = ''
    local: int = 0

    def is_visible_to(self, to_client):
        if (MessageTag.find_tag(self.name).local or self.local) and to_client.server:
            # logging.debug(f"Not relaying local tag {self} to server {self.name}")
            return 0
        return to_client.has_capability("message-tags")

    def filter_value(self, target):
        """
        Do nothing by default.
        """
        pass

    @property
    def string(self):
        return f"{self.name}{'=' + self.value if self.value else ''}"

    @staticmethod
    def find_tag(name):
        if not name:
            return
        for tag in MessageTag.table:
            if tag.name == name:
                return tag
            if '/' in name:
                for value in name.split('/'):
                    if value == tag.name:
                        return tag

    @staticmethod
    def add(tag):
        MessageTag.table.append(tag)

    @staticmethod
    def filter_tags(mtags, destination):
        # Don't copy.
        end_tags = []
        for tag in mtags:
            end_tags.append(tag)

        for tag in list(mtags):
            if not tag.is_visible_to(destination):
                end_tags.remove(tag)
                continue
            if filtered_tag := tag.filter_value(destination):
                end_tags.remove(tag)
                end_tags.append(filtered_tag)

        return end_tags


@dataclass(eq=False)
class ListEntry:
    mask: str = ''
    set_by: str = ''
    set_time: int = 0


@dataclass(eq=False)
class ModDataInfo:
    name: str = ''
    value: str = ''
    sync: int = 0


@dataclass(eq=False)
class ModData:
    @staticmethod
    def get_from_client(client: Client, name: str):
        return next((md for md in client.moddata if md.name == name), 0)

    @staticmethod
    def add_to_client(client: Client, name: str, value: str, sync: int = 1):
        if not (md := ModData.get_from_client(client, name)):
            md = ModDataInfo()
            client.moddata.append(md)
        md.name = name
        md.value = value
        md.sync = sync
        # logging.debug(f"Added ModData '{md.name}' to {client.name}: '{md.value}'")
        if md.sync and client.id:
            data = f":{client.uplink.id} MD client {client.id} {md.name} :{md.value}"
            IRCD.send_to_servers(client, mtags=[], data=data)

    @staticmethod
    def remove_from_client(client: Client, name: str):
        if not (md := ModData.get_from_client(client, name)):
            return
        client.moddata.remove(md)
        # logging.debug(f"Removed ModData '{md.name}' from {client.name}")
        if md.sync:
            data = f":{client.uplink.id} MD client {client.id} {md.name} :"
            IRCD.send_to_servers(client, mtags=[], data=data)


class Numeric:
    RPL_WELCOME = 1, ":Welcome to the {} IRC Network {}!{}@{}"
    RPL_YOURHOST = 2, ":Your host is {}, running version {}"
    RPL_CREATED = 3, ":This server was created {} at {}"
    RPL_MYINFO = 4, "{} {} {} {}"
    RPL_ISUPPORT = 5, "{} :are supported by this server"
    RPL_MAP = 6, ":{:50s} {} [{}%] [Uptime: {}, lag: {}ms]"
    RPL_MAPEND = 7, ":End of /MAP"
    RPL_SNOMASK = 8, "+{} :Server notice mask"
    RPL_BOUNCE = 10, "{} {} :Please connect to this server"
    RPL_CLONES = 30, ":User {} is logged in {} times: {}"
    RPL_NOCLONES = 31, ":No clones found on this {}"
    RPL_STATSHELP = 210, "{} :- {}"
    RPL_STATSLINKINFO = 211, "{} {} {} {} {} {} {} {} :{}"
    RPL_ENDOFSTATS = 219, "{} :End of /STATS report"
    RPL_UMODEIS = 221, "{}"
    RPL_STATSGLINE = 223, "{} {} {} {} {} :{}"
    RPL_STATSSPAMF = 229, "{} {} {} {} {} {} {} {} :{}"
    RPL_STATSEXCEPTTKL = 230, "{} {} {} {} :{}"
    RPL_RULES = 232, ":- {}"
    RPL_STATSUPTIME = 242, "{}"
    RPL_STATSOLINE = 243, "{} {} * {} {} {}"
    RPL_STATSDEBUG = 249, ":{}"
    RPL_LUSERCLIENT = 251, ":There {} {} user{} and {} invisible on {} server{}"
    RPL_LUSEROP = 252, "{} :IRC Operator{} online",
    RPL_LUSERUNKNOWN = 253, "{} :unknown connection{}"
    RPL_LUSERCHANNELS = 254, "{} :channel{} in use"
    RPL_LUSERME = 255, ":I have {} client{} and {} server{}"
    RPL_ADMINME = 256, ":Administrative info about {}"
    RPL_ADMINLOC1 = 257, ":{}"
    RPL_ADMINLOC2 = 258, ":{}"
    RPL_ADMINEMAIL = 259, ":{}"
    RPL_LOCALUSERS = 265, ":{} user{} on this server. Max: {}"
    RPL_GLOBALUSERS = 266, ":{} user{} on entire network. Max: {}"
    RPL_WHOISCERTFP = 276, "{} :has client certificate fingerprint {}"
    RPL_ACCEPTLIST = 281, "{}"
    RPL_ENDOFACCEPT = 282, "End of /ACCEPT list."
    RPL_HELPTLR = 292, ":{}"

    RPL_AWAY = 301, "{} :{}"
    RPL_USERHOST = 302, ":{}"
    RPL_TEXT = 304, ":{}"
    RPL_ISON = 303, ":{}"
    RPL_UNAWAY = 305, ":You are no longer marked as being away"
    RPL_NOWAWAY = 306, ":You have been marked as being away"
    RPL_WHOISREGNICK = 307, "{} :is identified for this nick"
    RPL_RULESSTART = 308, ":- {} Rules -"
    RPL_ENDOFRULES = 309, ":End of RULES"
    RPL_WHOISUSER = 311, "{} {} {} * :{}"
    RPL_WHOISSERVER = 312, "{} {} :{}"
    RPL_WHOISOPERATOR = 313, "{} :is {}{}"
    RPL_WHOWASUSER = 314, "{} {} {} * :{}"
    RPL_ENDOFWHO = 315, "{} :End of /WHO list."
    RPL_WHOISIDLE = 317, "{} {} {} :seconds idle, signon time"
    RPL_ENDOFWHOIS = 318, "{} :End of /WHOIS list."
    RPL_WHOISCHANNELS = 319, "{} :{}"
    RPL_WHOISSPECIAL = 320, "{} :{}"
    RPL_LISTSTART = 321, "Channel :Users  Name"
    RPL_LIST = 322, "{} {} :{} {}"
    RPL_LISTEND = 323, ":End of /LIST"
    RPL_CHANNELMODEIS = 324, "{} +{} {}"
    RPL_CREATIONTIME = 329, "{} {}"
    RPL_WHOISACCOUNT = 330, "{} {} :is using account"
    RPL_NOTOPIC = 331, "{} :No topic is set."
    RPL_TOPIC = 332, "{} :{}"
    RPL_TOPICWHOTIME = 333, "{} {} {}"
    RPL_WHOISBOT = 335, "{} :is a bot on {}"
    RPL_INVITING = 341, "{} {}"
    RPL_INVEXLIST = 346, "{} {} {} {}"
    RPL_ENDOFINVEXLIST = 347, "{} :End of Channel Invite List"
    RPL_EXLIST = 348, "{} {} {} {}"
    RPL_ENDOFEXLIST = 349, "{} :End of Channel Exception List"
    RPL_VERSION = 351, "{} {} [{}]"
    RPL_WHOREPLY = 352, "{} {} {} {} {} {} :{} {}"
    RPL_NAMEREPLY = 353, "= {} :{}"
    RPL_WHOSPCRPL = 354, "{}"
    RPL_LINKS = 364, "{} {} :{} {}"
    RPL_ENDOFLINKS = 365, ":End of LINKS"
    RPL_ENDOFNAMES = 366, "{} :End of /NAMES list."
    RPL_BANLIST = 367, "{} {} {} {}"
    RPL_ENDOFBANLIST = 368, "{} :End of Channel Ban List."
    RPL_ENDOFWHOWAS = 369, "{} :End of /WHOWAS list."
    RPL_INFO = 371, ":{}"
    RPL_MOTD = 372, ":- {}"
    RPL_MOTDSTART = 375, ":{} - Message of the Day"
    RPL_ENDOFMOTD = 376, ":End of /MOTD command."
    RPL_WHOISHOST = 378, "{} :is connecting from {}@{} {}"
    RPL_WHOISMODES = 379, "{} :is using modes: +{}{}"
    RPL_YOUREOPER = 381, ":You are now an IRC Operator."
    RPL_REHASHING = 382, "{} :Rehashing"
    RPL_IRCOPS = 386, ":{}"
    RPL_TIME = 391, ":{}"
    RPL_ENDOFIRCOPS = 387, ":End of /IRCOPS."
    RPL_HOSTHIDDEN = 396, "{} :is now your displayed host"

    RPL_LOGON = 600, "{} {} {} {} :logged online"
    RPL_LOGOFF = 601, "{} {} {} {} :logged offline"
    RPL_WATCHOFF = 602, "{} {} {} {} :stopped watching"
    RPL_WATCHSTAT = 603, ":You have {} and are on {} WATCH entries"
    RPL_NOWON = 604, "{} {} {} {} :is online"
    RPL_NOWOFF = 605, "{} {} {} {} :is offline"
    RPL_WATCHLIST = 606, ":{}"
    RPL_ENDOFWATCHLIST = 607, ":End of WATCH {}"
    RPL_OTHERUMODEIS = 665, "{} {}"
    RPL_WHOISSECURE = 671, "{} :is using a secure connection"

    RPL_TARGUMODEG = 716, "{} :has usermode +g"
    RPL_TARGNOTIFY = 717, "{} :has been informed of your request, awaiting reply"
    RPL_UMODEGMSG = 718, "{} {} :is messaging you, and you have umode +g."
    RPL_MONONLINE = 730, ":{}"
    RPL_MONOFFLINE = 731, ":{}"
    RPL_MONLIST = 732, ":{}"
    RPL_ENDOFMONLIST = 733, ":End of MONITOR list."
    RPL_MONLISTFULL = 734, ":Monitor list is full."

    RPL_LOGGEDIN = 900, "{} {} :You are now logged in as {}"
    RPL_LOGGEDOUT = 901, "{} :You are now logged out"
    RPL_NICKLOCKED = 902, ":You must use a nick assigned to you."
    RPL_SASLSUCCESS = 903, ":SASL authentication successful"

    ERR_NOSUCHNICK = 401, "{} :No such nick"
    ERR_NOSUCHSERVER = 402, "{} :No such server"
    ERR_NOSUCHCHANNEL = 403, "{} :No such channel"
    ERR_CANNOTSENDTOCHAN = 404, "{} :{}"
    ERR_WASNOSUCHNICK = 406, "{} :There was no such nickname"
    ERR_INVALIDCAPCMD = 410, "{} :Unknown CAP command"
    ERR_NORECIPIENT = 411, ":No recipient given'"
    ERR_NOTEXTTOSEND = 412, ":No text to send"
    ERR_UNKNOWNCOMMAND = 421, "{} :Unknown command"
    ERR_NOMOTD = 422, ":MOTD File is missing"
    ERR_NONICKNAMEGIVEN = 431, ":No nickname given"
    ERR_ERRONEUSNICKNAME = 432, "{} :Erroneous nickname (Invalid: {})"
    ERR_NICKNAMEINUSE = 433, "{} :Nickname is already in use"
    ERR_NORULES = 434, ":RULES File is missing"
    ERR_NICKTOOFAST = 438, "{} :Nick change too fast. Please wait a while before attempting again."
    ERR_SERVICESDOWN = 440, ":Services are currently down. Please try again later."
    ERR_USERNOTINCHANNEL = 441, "{} {} :User not on channel"
    ERR_NOTONCHANNEL = 442, "{} :You're not on that channel"
    ERR_USERONCHANNEL = 443, "{} :is already on channel {}"
    ERR_NONICKCHANGE = 447, ":{} Nick changes are not allowed on this channel"
    ERR_FORBIDDENCHANNEL = 448, "{} {}"
    ERR_NOTREGISTERED = 451, "You have not registered"
    ERR_ACCEPTEXIST = 457, "{} :does already exist on your ACCEPT list."
    ERR_ACCEPTNOT = 458, "{} :is not found on your ACCEPT list."
    ERR_NEEDMOREPARAMS = 461, ":{} Not enough parameters"
    ERR_ALREADYREGISTRED = 462, ":You may not reregister"
    ERR_PASSWDMISMATCH = 464, "Password mismatch"
    ERR_CHANNELISFULL = 471, "{} :Cannot join channel (+l)"
    ERR_UNKNOWNMODE = 472, "{} :unknown mode"
    ERR_INVITEONLYCHAN = 473, "{} :Cannot join channel (+i)"
    ERR_BANNEDFROMCHAN = 474, "{} :Cannot join channel (+b)"
    ERR_BADCHANNELKEY = 475, "{} :Cannot join channel (+k)"
    ERR_NEEDREGGEDNICK = 477, "{} :Cannot join cannel: you need a registered nickname"
    ERR_BANLISTFULL = 478, "{} {} :Channel {} list is full"
    ERR_NOPRIVILEGES = 481, ":Permission denied - You do not have the correct IRC Operator privileges"
    ERR_CHANOPRIVSNEEDED = 482, "{} :You're not a channel operator"
    ERR_ATTACKDENY = 484, "{} :Cannot kick protected user {}"
    ERR_KILLDENY = 485, ":Cannot kill protected user {}"
    ERR_SERVERONLY = 487, ":{} is a server-only command"
    ERR_SECUREONLY = 489, "{} :Cannot join channel (not using a secure connection)"
    ERR_NOOPERHOST = 491, ":No O:lines for your host"

    ERR_UMODEUNKNOWNFLAG = 501, "{} :Unknown MODE flag"
    ERR_USERSDONTMATCH = 502, ":Not allowed to change mode of other users"
    ERR_TOOMANYWATCH = 512, "{} :Maximum size for WATCH-list is 128 entries"
    ERR_NOINVITE = 518, ":Invite is disabled on channel {} (+V)"
    ERR_OPERONLY = 520, "{} :Cannot join channel (IRCOps only)"
    ERR_CANTSENDTOUSER = 531, "{} :{}"

    ERR_INVALIDMODEPARAM = 696, "{} {} {} :{}"

    ERR_SASLFAIL = 904, ":SASL authentication failed"
    ERR_SASLTOOLONG = 905
    ERR_SASLABORTED = 906, ":SASL authentication aborted"
    ERR_SASLALREADY = 907, ":You have already authenticated using SASL"
    ERR_CANNOTDOCOMMAND = 972, "{} :{}"
    ERR_CANNOTCHANGECHANMODE = 974, "{} :{}"


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
        if not Capability.find_cap(capname):
            cap = Capability()
            cap.name = capname
            cap.value = value
            Capability.table.append(cap)
            # logging.info(f"Added new capability: {cap.string}")
            for client in [c for c in IRCD.local_users() if c.has_capability("cap-notify")]:
                client.send([], f":{IRCD.me.name} CAP {client.name} NEW :{cap.string}")

    @staticmethod
    def remove(capname):
        if not (cap := Capability.find_cap(capname)):
            return
        Capability.table.remove(cap)
        for client in [c for c in IRCD.local_users() if c.has_capability("cap-notify")]:
            client.send([], f":{IRCD.me.name} CAP {client.name} DEL :{cap.string}")

    @property
    def string(self):
        return f"{self.name}{'=' + self.value if self.value else ''}"

    def __repr__(self):
        return f"<Capability '{self.string}'>"


class Stat:
    table = []
    letter = ''
    func = None

    @staticmethod
    def add(module, func, letter, desc):
        if Stat.get(letter):
            logging.error(f"Attempting to add duplicate STAT: {letter}")
            return
        stat = Stat()
        stat.module = module
        stat.func = func
        stat.letter = letter
        stat.desc = desc
        Stat.table.append(stat)

    @staticmethod
    def get(letter):
        return next((s for s in Stat.table if s.letter == letter), 0)

    def show(self, client):
        self.func(client)
        client.sendnumeric(Numeric.RPL_ENDOFSTATS, self.letter)
        msg = f'* Stats "{self.letter}" requested by {client.name} ({client.user.username}@{client.user.realhost})'
        IRCD.send_snomask(client, 's', msg)


class Extban:
    table = []
    symbol = "~"

    @staticmethod
    def add(extban):
        if not hasattr(extban, "flag"):
            error = f"Could not add extban: 'flag' missing"
            logging.error(error)
            exit()
        if not hasattr(extban, "name"):
            error = f"Could not add extban: 'name' missing"
            logging.error(error)
            exit()
        exists = next((e for e in Extban.table if e.flag == extban.flag), 0)
        if exists:
            logging.error(f"Could not add extban: flag '{extban.flag}' already exists: {exists}")
            exit()

        if not hasattr(extban, "paramcount"):
            logging.error(f"Paramcount missing in extban '{extban.flag}'")
            exit()

        if not hasattr(extban, "is_ok"):
            logging.error(f"No is_ok() method for extban: {extban}")
            exit()

        if not hasattr(extban, "is_match"):
            extban.is_match = lambda a, b, c: 0

        for eb in list(Extban.table):
            if eb.flag == extban.flag:
                Extban.table.remove(eb)

        Extban.table.append(extban)
        extban_flags = ''.join([e.flag for e in Extban.table])
        Isupport.add("EXTBAN", Extban.symbol + ',' + extban_flags)

    @staticmethod
    def is_extban(client, channel, action, mode, param):
        if param.startswith(Extban.symbol):
            if len(param.split(':')) < 2:
                return -1
            param_split = param.split(':')
            name = param_split[0][1:]
            for extban in Extban.table:
                valid = (extban.name and extban.name == name) or extban.flag == name
                if not valid:
                    continue
                if name == extban.flag:
                    param_split[0] = Extban.symbol + extban.name
                param = ':'.join(param_split)
                if returned_param := extban.is_ok(client, channel, action, mode, param):
                    return returned_param
            return -1
        return 0

    @staticmethod
    def find(param: str):
        return next((e for e in Extban.table if param in [Extban.symbol + e.name, Extban.symbol + e.flag]), 0)

    @staticmethod
    def convert_param(param: str, convert_to_name: int = 1) -> str:
        """
        Converts extban flags or names to their counterparts.

        +b ~t:1:~a:Sirius       ->  +b ~timed:1:~account:Sirius

        This does not work:
        +b ~t:1:~T:block:xd     ->  ~b ~timed:1:~text:block:xd
        """

        param_split = param.split(':')
        converted = []
        for item in param_split:
            if item[0] == Extban.symbol:
                if main_ext := Extban.find(item):
                    converted.append(Extban.symbol + main_ext.flag if not convert_to_name else Extban.symbol + main_ext.name)
                else:
                    # Invalid extban, returning raw param.
                    return param
            else:
                converted.append(item)

        converted_str = ':'.join(converted)
        return converted_str


class Hook:
    DENY = hook()
    ALLOW = hook()
    CONTINUE = hook()

    # This is called every 1 second, or as soon as new data is being handled.
    LOOP = hook()

    # Gets called before sending to a socket.
    # You cannot reject this.
    # Arguments:        Message object
    PACKET_SEND = hook()

    # Called when a packet is being read or sent.
    # Arguments         from            Sender of this data.
    #                   to              Direction to send the data to.
    #                   intended_to     Actual client this data is for.
    #                   data            List of data, so that it can be modified by modules.
    PACKET = hook()

    # Called when preparing an outgoing new message. Used to assign tags etc.
    # This is used by hooks and is currently only called in the early stages of PRIVMSG, JOIN, PART and MODE.
    # Modules can use this hook to generate a new message and add tags.
    NEW_MESSAGE = hook()

    # This hook is called early in the connection phase.
    # Basically the only useful information in this phase is the IP address and the socket object of the connection.
    NEW_CONNECTION = hook()

    # Used by modules to check if the handshake is completed.
    # Arguments:        Client
    IS_HANDSHAKE_FINISHED = hook()

    # This is when the connection has been accepted, but still needs to go through verification phase
    # against configuration and internal block lists.
    PRE_CONNECT = hook()

    # This is further down the connection process, when all internal checks have been passed.
    # When this hook gets called, the local client is already registered on the server.
    # This hook is generally not used to deny/exit clients. Use PRE_CONNECT for that.
    # Argument:                 User object.
    LOCAL_CONNECT = hook()

    # When a new remote user is introduced, this hook gets called.
    # Argument:         User object.
    REMOTE_CONNECT = hook()

    # Called right before reading a socket.
    # Arguments:        socket
    # Return value is ignored.
    PRE_SOCKREAD = hook()

    # Called after reading a socket, but before performing any commands.
    # Used in IRCv3 reply tags.
    # Arguments:        client, recv
    # Return value is ignored.
    POST_SOCKREAD = hook()

    # Called in the early phase of changing channel modes.
    # Arguments:
    # client            Client changing the mode.
    # channel           Channel on which the mode is being changed.
    # modebuf           Current mode buffer
    # parambuf          Current parameter buffer
    # action            Action: + or -
    # mode              Mode char
    # param_mode        Param mode, or None if none
    # Return:           Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_CHANNEL_MODE = hook()

    # Called when a local user or server changes channel modes.
    # Arguments:        client, channel, modebuf, parambuf
    LOCAL_CHANNEL_MODE = hook()

    # Called after a remote user changes channel modes.
    # Arguments:        client, channel, modebuf, parambuf
    REMOTE_CHANNEL_MODE = hook()

    # Called early when a remote user or server changes a mode.
    # You can not deny this hook.
    # Arguments:
    # client            Client changing the mode.
    # channel           Channel on which the mode is being changed.
    # modebuf           Current mode buffer
    # parambuf          Current parameter buffer
    # action            Action: + or -
    # mode              Mode char
    # param_mode        Param mode, or None if none
    PRE_REMOTE_CHANNEL_MODE = hook()

    # Called before a local nick change.
    # Arguments:        client, newnick
    # Return:           Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_NICKCHANGE = hook()

    # Called after a local user changes his nickname
    # Arguments:        client, newnick
    LOCAL_NICKCHANGE = hook()

    # Called after a remote user changes his nickname
    # Arguments:    client, newnick
    REMOTE_NICKCHANGE = hook()

    # Called before a local user attempts to join a channel.
    # Arguments:    client, channel, key
    # Return:       Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_JOIN = hook()

    # Gets called when a local user joins a channel.
    # Arguments:    client, channel
    LOCAL_JOIN = hook()

    # Gets called when a remote user joins a channel.
    # Arguments:    client, channel
    REMOTE_JOIN = hook()

    # Called when a local user wants to part a channel.
    # Arguments:    client, channel, reason
    # Returns:      part reason, if is has been changed. Return nothing to keep original part reason.
    PRE_LOCAL_PART = hook()

    # Called after a local user leaves a channel.
    # Arguments:    client, channel, reason
    LOCAL_PART = hook()

    # Called after a remote user leaves a channel.
    # Arguments:    client, channel, reason
    REMOTE_PART = hook()

    # Used to check if a user can join a channel.
    # Arguments:    client, channel, key
    # Returns:      0 to allow, RPL to deny.
    CAN_JOIN = hook()

    # Called when a user fails to join a channel due to a channel mode.
    # Arguments:    client, channel, mode
    JOIN_FAIL = hook()

    # Called after a user is allowed to join the channel,
    # but before broadcasting its join to users.
    # It will loop over all users in the channel on each call
    # to check if `client_1` may see `client_2` on the channel.
    # Arguments:    client_1, client_2, channel
    # Return:       Hook.DENY or Hook.CONTINUE
    VISIBLE_ON_CHANNEL = hook()

    # Called before a local user broadcasts his/her quit.
    # Arguments:    client, reason
    # Return:       reason, or None
    PRE_LOCAL_QUIT = hook()

    # Called after a local user quits the server.
    # Arguments:    client, reason
    LOCAL_QUIT = hook()

    # Called after a remote user quits the network.
    # Arguments:    client, reason
    REMOTE_QUIT = hook()

    # Called when a new channel is created.
    # Arguments:    client, channel
    CHANNEL_CREATE = hook()

    # Called when a channel is destroyed.
    # Arguments:    client, channel
    CHANNEL_DESTROY = hook()

    # Called before a local user sends a channel message.
    # The Privmsg object has the `msg` attribute, which contains the message beint sent.
    # Arguments:    client, channel, message as list so it can be modified
    # Returns:      Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_CHANMSG = hook()

    # Called before a remote user sends a channel message.
    # This event cannot be denied.
    # Arguments:    client, channel, message
    PRE_REMOTE_CHANMSG = hook()

    # This is called after a local user has sent a channel message.
    # Arguments:    client, channel, message
    LOCAL_CHANMSG = hook()

    # Called when a remote user sends a channel message.
    # Arguments:    client, channel, message
    REMOTE_CHANMSG = hook()

    # Called before a local user sends a private user message.
    # Arguments:    client, target, message as list, so it can be modified.
    # Return:       Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_USERMSG = hook()

    # Called before a remote user sends a private user message.
    # Arguments:    client, target, message
    # This event cannot be denied.
    PRE_REMOTE_USERMSG = hook()

    # Called when a local user sends a private message message.
    # Arguments:    client, target, message
    LOCAL_USERMSG = hook()

    # Called when a remote user sends a private message.
    # Arguments:    client, channel, message
    REMOTE_USERMSG = hook()

    # Check whether a user can send a privsmg to another user. This includes remote users (for callerid)
    # The message cannot be modified.
    # Modules using this hook are responsible to deliver any error messages back to the client.
    # Arguments:    client, target, message
    # Return:       Hook.DENY or Hook.CONTINUE
    CAN_SEND_TO_USER = hook()

    # Check whether a user can send a privsmg to a channel.
    # The message cannot be modified.
    # Modules using this hook are responsible to deliver any error messages back to the client.
    # Arguments:    client, channel object, message
    # Return:       Hook.DENY or Hook.CONTINUE
    CAN_SEND_TO_CHANNEL = hook()

    PRE_LOCAL_CHANNOTICE = hook()
    PRE_REMOTE_CHANNOTICE = hook()

    LOCAL_CHANNOTICE = hook()
    REMOTE_CHANNOTICE = hook()

    PRE_LOCAL_USERNOTICE = hook()
    PRE_REMOTE_USERNOTICE = hook()

    # Called when a locel user sends a user notice.
    # Arguments:    client, user, msg
    LOCAL_USERNOTICE = hook()

    # Called when a remote user sends a user notice.
    # Arguments:    client, user, msg
    REMOTE_USERNOTICE = hook()

    # Called when a local client wants to kick a user off a channel.
    # Arguments:    client, target_client, channel, reason
    # Return:       Hook.DENY to deny.
    CAN_KICK = hook()

    # Called after a local user kicked gets kicked off a channel.
    # Arguments:    client, kick_user, channel, reason
    LOCAL_KICK = hook()

    # Called after a remote user kicked gets kicked off a channel.
    # Arguments:    client, kick_user, channel, reason
    REMOTE_KICK = hook()

    # Called when a modebar has been set on a channel.
    # Arguments:    client, channel, modebar, param
    MODEBAR_ADD = hook()

    # Called when a modebar has been unset from a channel.
    # Arguments:    client, channel, modebar, param
    MODEBAR_DEL = hook()

    # Called after a user mode has been changed.
    # Arguments:   client, target, current_modes, new_modes
    UMODE_CHANGE = hook()

    # Called before a user sets /away status.
    # Arguments:    client, reason
    # Can be rejected by returning Hook.DENY
    PRE_AWAY = hook()

    # Called after a user successfully set /away status.
    AWAY = hook()

    # Called very early when a server requests a link, before negotiation.
    # Arguments:    server
    SERVER_LINK_IN = hook()

    # Called after basic negotation, but before syncing users and channels.
    # Used to negotiate CAPs.
    # Arguments:    remote_server
    SERVER_LINK_POST_NEGOTATION = hook()

    # Called very early when we request a link, before the socket connects.
    # Arguments:    server
    SERVER_LINK_OUT = hook()

    # Called after all users and channels have been synced, but before we reach their EOS.
    # Arguments:    server
    SERVER_SYNC = hook()

    # Called after everything has been synced from the remote server, after we reached their EOS.
    # Arguments:    server
    SERVER_SYNCED = hook()

    # Called when a server disconnects.
    # Arguments:    server
    SERVER_DISCONNECT = hook()

    # Called before a local user performs a command.
    # Arguments:    client, recv
    # Return:       Hook.DENY or Hook.CONTINUE
    PRE_COMMAND = hook()

    # Called after a local user performs a command.
    # Arguments:    client, recv
    POST_COMMAND = hook()

    # Called before a local user changes a channel topic.
    # Arguments:    client, channel, newtopic
    # Return:       Hook.DENY or Hook.CONTINUE
    PRE_LOCAL_TOPIC = hook()

    # Called after a user changes a channel topic.
    # Arguments:    client, channel, newtopic
    TOPIC = hook()

    # Called when a user logs in or out of a services account.
    # Arguments:    client
    ACCOUNT_LOGIN = hook()

    # Called when /whois is performed.
    # Arguments:    client, target, whoislines: list
    WHOIS = hook()

    # Called when a /who is performed.
    WHO_STATUS = hook()

    # Called when a /mode list is requested.
    CHAN_LIST_ENTRY = hook()

    # This dictionary is holding callbacks for each hook type.
    hooks = {}

    @staticmethod
    def call(hook_type, args=(), kwargs=None):
        """
        :param hook_type:   Hook type
        :param args:        Command arguments to pass to the hook callback
        :param kwargs:      Command keyword arguments to pass to the book callback
        :return:            0 for success, anything else for process
        """
        if not kwargs:
            kwargs = {}
        default = Hook.CONTINUE, None  # Defaults.
        if hook_type not in Hook.hooks:
            # Not implemented yet.
            return default

        hooks_sorted_priority = sorted((hook for hook in Hook.hooks[hook_type]), key=lambda hook: hook[1], reverse=True)
        for callback, priority in hooks_sorted_priority:
            try:
                result = callback(*args, **kwargs)
                yield result, callback
            except Exception as ex:
                # logging.error(f"Args: {args}")
                # logging.exception(f"Exception in callback {callback}, args {args}: {ex}")
                break

    @staticmethod
    def add(hook_type, callback, priority=0):
        if hook_type not in Hook.hooks:
            Hook.hooks[hook_type] = []
        for cb, prio in list(Hook.hooks[hook_type]):
            if cb.__module__ == callback.__module__:
                Hook.hooks[hook_type].remove((cb, prio))

        Hook.hooks[hook_type].append((callback, priority))

    @staticmethod
    def remove(callback):
        for hook in list(Hook.hooks):
            for hook_cb, priority in list(Hook.hooks[hook]):
                if hook_cb == callback:
                    Hook.hooks[hook].remove((callback, priority))
                    logging.debug(f"Unhooked: {hook} -> {callback}")


class Batch:
    """ All active batches. """
    pool = []

    def __init__(self, started_by, batch_type=None, additional_data=''):
        self.label = ''.join((random.choice(string.ascii_letters + string.digits) for x in range(10)))
        self.tag = MessageTag.find_tag("batch")(value=self.label)
        # We need to be able to refer to whoever started this batch.
        # Also keep in mind that servers can start batches too, for example with netjoin and netsplit.
        self.started_by = started_by

        self.batch_type = batch_type
        self.additional_data = additional_data
        self.users = []
        self.start()

    @staticmethod
    def create_new(started_by, batch_type=None, additional_data=''):
        batch = Batch(started_by=started_by, batch_type=batch_type, additional_data=additional_data)
        return batch

    @staticmethod
    def check_batch_event(mtags, started_by, target_client, event):
        """
        :param mtags:           Message tags list to add BATCH tag to.
        :param started_by:      Client that started this batch.
        :param target_client:   Target client to show this BATCH event to.
        :param event:           Batch event: netjoin or netsplit.
        """
        # logging.warning(f"Looking for a batch started by {started_by.name}")
        for batch in Batch.pool:
            # logging.warning(f"Found a batch started by {batch.started_by.name}")
            if batch.started_by in [started_by, started_by.uplink, started_by.direction] and batch.batch_type == event:
                if (batch.tag.name, batch.tag.value) not in [(t.name, t.value) for t in mtags]:
                    mtags[0:0] = [batch.tag]
                    # mtags.append(batch.tag)
                if target_client not in batch.users:
                    batch.announce_to(target_client)

    def start(self, batch_id=None):
        # TODO: Maybe start/end BATCH with an internal ID?
        for user in [u for u in self.users if u.has_capability("batch")]:
            data = f":{IRCD.me.name} BATCH +{self.label}{' ' + self.batch_type if self.batch_type else ''}" \
                   f"{' ' + self.additional_data if self.additional_data else ''}"
            user.send([], data)
        Batch.pool.append(self)

    def end(self, batch_id=None):
        # TODO: Maybe start/end BATCH with an internal ID?
        if self in Batch.pool:
            Batch.pool.remove(self)
        for user in self.users:
            user.send([], f":{IRCD.me.name} BATCH -{self.label}")
        for client in IRCD.global_clients():
            for tag in list(client.mtags):
                if tag.name == "batch" and tag.value == self.label:
                    client.mtags.remove(tag)
        self.users = []

    def announce_to(self, client):
        if not self.tag.is_visible_to(client):
            return
        if client not in self.users:
            data = f":{IRCD.me.name} BATCH +{self.label} {self.batch_type}{' ' + self.additional_data if self.additional_data else ''}"
            client.send([], data)
            self.users.append(client)

    @staticmethod
    def find_batch_by(started_by):
        return next((batch for batch in Batch.pool if batch.started_by == started_by), 0)

    def __repr__(self):
        return f"<Batch '{self.label} [{self.started_by.name}]'>"


@dataclass
class TklFlag:
    flag: str = ''
    name: str = ''
    what: str = ''
    host_format: int = 1
    is_global: int = 0
    allow_eline: int = 1
    is_extended: int = 0


class Tkl:
    table = []
    flags = []

    ext_names = {
        "~account:": "~account:",
        "~a:": "~account:",
        "~certfp:": "~certfp:",
        "~S:": "~certfp:",
    }

    def __init__(self, _type, ident, host, bantypes, expire, set_by, set_time, reason):
        self.type = _type
        self.ident = ident
        self.host = host
        self.bantypes = bantypes
        self.expire = expire
        self.set_by = set_by
        self.set_time = set_time
        self.reason = reason

    @staticmethod
    def add_flag(flag: str, name: str, what: str, host_format: int, is_global: int, allow_eline: int = 0, is_extended: int = 0):
        """
        :param host_format:         1 = ident@host, 0 = raw (only host part)
                                    Determine the format shown in server notices.
                                    Raw is generally only used for Q:lines and extended server bans
                                    so that it doesn't show it as *@[...].
        """
        tkl_flag = TklFlag(flag, name, what, host_format, is_global, allow_eline, is_extended)
        Tkl.flags.append(tkl_flag)

    @staticmethod
    def get_flag_of_what(what: str):
        return next((tkl for tkl in Tkl.flags if tkl.what == what), 0)

    @staticmethod
    def get_flags_host_format():
        return ''.join([tkl.flag for tkl in Tkl.flags if tkl.host_format])

    @staticmethod
    def global_flags():
        return ''.join([t.flag for t in Tkl.flags if t.is_global])

    @staticmethod
    def valid_flags():
        return ''.join([t.flag for t in Tkl.flags])

    @staticmethod
    def valid_eline_flags():
        return ''.join([t.flag for t in Tkl.flags if t.allow_eline])

    @property
    def name(self):
        return next((t.name for t in Tkl.flags if t.flag == self.type), None)

    def is_extended(self):
        return 1 if self.ident in Tkl.ext_names else 0

    @property
    def mask(self):
        return Tkl.get_mask(self.type, self.ident, self.host)

    @staticmethod
    def get_mask(tkltype, ident, host):
        if ident in Tkl.ext_names:
            return f"{Tkl.ext_names[ident]}{host}"
        elif tkltype in Tkl.get_flags_host_format():
            return f"{ident}@{host}"
        else:
            return host

    @staticmethod
    def exists(tkltype, mask):
        for tkl in Tkl.table:
            if tkl.type == tkltype and tkl.mask == mask:
                return tkl
        return 0

    @staticmethod
    def valid_extban(mask):
        """ Returns the converted ident if this mask is a valid extban, otherwise 0. """
        ident = mask.split(':')[0] + ':'
        if ident in Tkl.ext_names:
            return Tkl.ext_names[ident]
        return 0

    @property
    def is_global(self):
        return self.type in Tkl.global_flags()
        # return 1 if (self.type in Tkl.global_flags() or (self.type == 'E' and [t for t in self.bantypes if t in Tkl.global_flags()])) else 0

    @staticmethod
    def add(client, flag, ident, host, bantypes, set_by, expire, set_time, reason):
        """
        client:     Source performing the add.
        bantypes:   Only applicable with /eline. Specifies with bantypes to except.
        """
        logging.debug(f"TKL add from client ID: {client.id} ({client.name})")
        if flag not in Tkl.valid_flags():
            return logging.warning(f"Attempted to add non-existing TKL {flag} from {client.name}")
        mask = Tkl.get_mask(flag, ident, host)
        update, exists = 0, 0
        if tkl := Tkl.exists(flag, mask):
            exists = 1
            if int(expire) != int(tkl.expire) or tkl.reason != reason:
                update = 1
                tkl.expire = expire
                tkl.reason = reason
                tkl.bantypes = bantypes

        expire = int(expire)
        if expire != 0:
            d = datetime.fromtimestamp(expire).strftime('%a %b %d %Y')
            t = datetime.fromtimestamp(expire).strftime('%H:%M:%S %Z')
        else:
            d, t = None, None

        expire_string = f'{"never" if expire == 0 else d + " " + t}'

        if not tkl:
            tkl = Tkl(flag, ident, host, bantypes, expire, set_by, int(time()), reason)
            Tkl.table.append(tkl)
            matches = Tkl.find_matches(tkl)
            if flag in "kGzZ":
                for c in matches:
                    tkl.do_ban(c)

        bt_string = f" [{bantypes}]" if bantypes != '*' else ''
        if not update and not exists or (update and IRCD.find_user(set_by.split('!')[0])):
            msg = f'*** {"Global " if tkl.is_global else ""}{tkl.name}{bt_string} {"active" if not update else "updated"} for {tkl.mask} by {set_by} [{reason}] expires on: {expire_string}'
            sync = not tkl.is_global
            IRCD.log(client, "info", "tkl", "TKL_ADD", msg, sync=sync)
        if tkl.is_global:
            if flag == 'E':
                local_bantypes = ''
                for bt in [bt for bt in bantypes if bt in Tkl.global_flags()]:
                    local_bantypes += bt
                bantypes = local_bantypes
            data = f":{client.id} TKL + {flag} {ident} {host} {bantypes} {set_by} {expire} {set_time} :{reason}"
            IRCD.send_to_servers(client, [], data)

    @staticmethod
    def remove(client, flag, ident, host):
        """
        client:    Source performing the remove.
        """
        if flag not in Tkl.valid_flags():
            return
        for tkl in list(Tkl.table):
            if tkl.type == flag and (tkl.ident, tkl.host) == (ident, host):
                if tkl.expire and client != IRCD.me and not client.user:
                    continue
                Tkl.table.remove(tkl)
                expire = 0
                if tkl.expire and int(time()) >= tkl.expire:
                    expire = 1
                date = f'{datetime.fromtimestamp(float(tkl.set_time)).strftime("%a %b %d %Y")} {datetime.fromtimestamp(float(tkl.set_time)).strftime("%H:%M:%S")}'
                msg = f'*** {"Expiring " if expire else ""}{"Global " if tkl.is_global else ""}{tkl.name} {tkl.mask} removed (set by {tkl.set_by} on {date}) [{tkl.reason}]'
                sync = not tkl.is_global
                IRCD.log(client, "info", "tkl", "TKL_DEL", msg, sync=sync)

                # TODO: Maybe also sync global TKL expires?
                #  Check if this has negative effects.
                if tkl.is_global and not expire:
                    data = f':{client.id} TKL - {flag} {tkl.ident} {tkl.host}'
                    IRCD.send_to_servers(client, [], data)

                if tkl.type == 's':
                    for shun_client in Tkl.find_matches(tkl):
                        if shun_client.is_shunned():
                            shun_client.flags.remove(Flag.CLIENT_SHUNNED)

    def do_ban(self, client):
        if client.exitted:
            return
        if client.local:
            client.sendnumeric(Numeric.RPL_TEXT, f"[{self.set_by.split('!')[0]}] {self.reason}")
            IRCD.server_notice(client, f"*** You are banned from this server: {self.reason}")
        client.exit("User has been banned from using this server")

    @staticmethod
    def find_tkl_by_mask(tkltype, mask):
        for tkl in [tkl for tkl in Tkl.table if tkl.type == tkltype]:
            if is_match(tkl.mask.lower(), mask.lower()):
                return tkl

    @staticmethod
    def is_match(client, tkltype):
        """
        Check if 'client' matches any TKL of type 'tkltype'
        If a match is found, the tkl object will be returned.
        Otherwise, None is returned.
        """
        if not client.user:
            return

        if client.has_permission("immune:server-ban"):
            return

        for tkl in [tkl for tkl in Tkl.table if tkl.type in tkltype]:
            if tkl.type == "k" and (client.has_permission("immune:server-ban:kline") or IRCD.is_except_client("kline", client)):
                continue
            if tkl.type == "G" and (client.has_permission("immune:server-ban:gline") or IRCD.is_except_client("gline", client)):
                continue
            if tkl.type == "z" and (client.has_permission("immune:server-ban:zline:local") or IRCD.is_except_client("zline", client)):
                continue
            if tkl.type == "Z" and (client.has_permission("immune:server-ban:zline:global") or IRCD.is_except_client("gzline", client)):
                continue
            if tkl.type == "s" and (client.has_permission("immune:server-ban:shun") or IRCD.is_except_client("shun", client)):
                continue

            if tkl.is_extended():
                if tkl.ident == "~account:":
                    if tkl.host == '0' and client.user.account == '*':
                        return tkl
                    if client.user.account.lower() == tkl.host.lower():
                        return tkl
                if tkl.ident == "~certfp:":
                    if fp := client.get_md_value("certfp"):
                        if tkl.host.lower() == fp.lower():
                            return tkl
                    else:
                        if tkl.host == '0':
                            return tkl
                continue
            if tkl.type in "GkZzs":
                ident = '*' if not client.user.username else client.user.username
                test_cases = [f"{ident.lower()}@{client.ip}", f"{ident.lower()}@{client.ip}"]
                for test in test_cases:
                    if is_match(tkl.mask.lower(), test):
                        if tkl.type == 's' and not client.is_shunned():
                            client.add_flag(Flag.CLIENT_SHUNNED)
                        return tkl

            elif tkl.type == "Q":
                if is_match(tkl.host.lower(), client.name.lower()):
                    return tkl

    @staticmethod
    def find_matches(tkl):
        matches = []
        for user_client in IRCD.local_users():
            if Tkl.is_match(user_client, tkl.type):
                matches.append(user_client)

        return matches

    def __index__(self, num):
        return Tkl.table[num]

    def __repr__(self):
        return f"<TKL '{self.type}' -> '{self.mask}'>"
