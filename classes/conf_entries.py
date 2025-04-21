import re
import time
import socket
import selectors
import ipaddress
import importlib

import OpenSSL.SSL

from handle.core import IRCD
from handle.functions import logging, is_match
from handle.handle_tls import create_ctx


class Mask:
    def __init__(self, block=None):
        self.mask = []
        self.ip = []
        self.account = []
        self.certfp = []
        self.country = []
        self.realname = []
        self.nick = []
        self.tls: int = 0
        self.identified: int = 0
        self.webirc: int = 0
        self.websockets: int = 0
        if block:
            self.parse_masks(block)

    @property
    def types(self):
        return list(self.__dict__.keys())

    def parse_masks(self, block):
        for item in block.get_items("mask"):
            if not (mask_what := item.get_single_value("mask").strip()):
                continue

            if mask_what in ("country", "account", "certfp", "realname", "nick", "ip"):
                mask_value = item.path[3]
                getattr(self, mask_what).append(mask_value)

            elif mask_what in ("tls", "identified", "webirc", "websockets"):
                mask_value = item.path[3]
                setattr(self, mask_what, mask_value == "yes")

            else:
                # Default mask format (user@host)
                mask_value = mask_what
                if mask_value not in self.mask:
                    self.mask.append(mask_value)

            if mask_value.strip():
                self.check_values(block=block, item=item, mask_what=mask_what, mask_value=mask_value)

    def check_values(self, block, item, mask_what=None, mask_value=None, normal_mask=0):
        from handle.validate_conf import conf_error

        match mask_what:

            case "certfp":
                if not re.match(r"[A-Fa-f0-9]{64}$", mask_value):
                    return conf_error(f"Invalid certfp: {mask_value} -- must be in SHA256 format: [A-Fa-f0-9]{64}", item=item)

            case "account":
                if mask_value[0].isdigit():
                    return conf_error(f"Invalid account name: {mask_value} -- cannot start with number", item=item)
                if invalid := {c for c in mask_value if c.lower() not in IRCD.NICKCHARS}:
                    return conf_error(f"Invalid account name: {mask_value} -- invalid characters: {''.join(invalid)}", item=item)

            case "ip":
                try:
                    ipaddress.ip_address(mask_value.replace('*', '0'))
                except ValueError:
                    return conf_error(f"Invalid IP address '{mask_value}'", item=item)

            case "country" | "realname":
                return

            case "tls" | "identified" | "webirc" | "websockets":
                if mask_value not in ["yes", "no"]:
                    return conf_error(f"Unknown mask value for {mask_what}: {mask_value}. Should either be 'yes' or 'no'.", item=item)

            case _:
                block_key = f"{block.name}:{block.value}"
                if block.name == "link":
                    if mask_what == '*':
                        check_ip = '0.0.0.0'
                    else:
                        check_ip = mask_what.replace('*', '0')
                    try:
                        ipaddress.ip_address(check_ip)
                    except ValueError as ex:
                        logging.exception(ex)
                        return conf_error(f"Invalid {block_key} mask '{mask_what}'. Must be a valid IP address", item=item)

                if block_key == "ban:nick":
                    if mask_value[0].isdigit():
                        return conf_error(f"Invalid account name: {mask_value} -- cannot start with number", item=item)
                    if invalid := {c for c in mask_value if c != '*' and c.lower() not in IRCD.NICKCHARS}:
                        return conf_error(f"Invalid account name: {mask_value} -- invalid characters: {''.join(invalid)}", item=item)

                elif block_key not in {"except:spamfilter"}:
                    """ Normal mask ident@host or IP """
                    if not re.match(r"^[\w*.]+@[\w*.]+$", mask_what):
                        if mask_what == '*':
                            check_ip = '0.0.0.0'
                        else:
                            check_ip = mask_what.replace('*', '0')
                        try:
                            ipaddress.ip_address(check_ip)
                        except ValueError:
                            return conf_error(f"Invalid {block_key} mask '{mask_what}'. Must be either an ident@host or IP", item=item)

    def is_match(self, client):
        ident = client.user.username if client.user else '*'
        usermask = f"{ident}@{client.user.realhost if client.user else client.name}"
        ipmask = f"{ident}@{client.ip}"

        checks = [
            (self.websockets, lambda _: client.websocket),
            (self.webirc, lambda _: client.webirc),
            (self.tls, lambda _: client.local and not client.local.tls),
            (self.identified, lambda _: client.user.account != '*'),
            (self.ip, lambda ip: is_match(ip, client.ip)),
            (self.certfp, lambda certfp: certfp == client.get_md_value("certfp")),
            (self.country, lambda country: country == client.get_md_value("country")),
            (self.account, lambda account: account == client.user.account),
            (self.nick and client.name != '*', lambda nick: is_match(nick, client.name)),
            (self.realname and client.info, lambda realname: is_match(realname, client.info)),
            (self.mask, lambda mask: is_match(mask, client.ip) or is_match(mask, usermask) or is_match(mask, ipmask))
        ]

        for condition, test in checks:
            if condition and any(test(item) for item in condition):
                return 1

        return 0

    def __repr__(self):
        return f"<Mask '{self.mask}'>"


class ConnectClass:
    def __init__(self, name, sendq, recvq, maxc):
        self.name = name
        self.sendq = int(sendq)
        self.recvq = int(recvq)
        self.max = int(maxc)
        IRCD.configuration.connectclass.append(self)

    def __repr__(self):
        return f"<Class '{self.name}'>"


class Allow:
    def __init__(self, mask: Mask, connectclass_name, maxperip):
        self.mask = mask
        self.connectclass_name = connectclass_name
        self.maxperip = int(maxperip)
        self.options = []
        self.password = ''
        IRCD.configuration.allow.append(self)

    def __repr__(self):
        return f"<Allow '{self.mask}:{self.maxperip}'>"


class Listen:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.options = []
        self.tls = 0
        self.tlsctx = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listening = 0
        self.cert = None
        self.key = None
        self.websockets = 0
        IRCD.configuration.listen.append(self)

    def start_listen(self, output=1):
        try:
            if self.tls and self.cert and self.key:
                self.tlsctx = create_ctx(cert=self.cert, key=self.key, name=IRCD.me.name)

            if not self.listening:
                ip = '' if self.ip == '*' else self.ip
                try:
                    self.sock.bind((ip, int(self.port)))
                except (PermissionError, OSError) as ex:
                    if ex.errno in [13, 10013]:
                        logging.error(f"[WebSockets] Could not bind to port '{self.port}': Permission denied.")
                        return
                    if ex.errno in [98, 48, 10048]:
                        logging.error(f"[WebSockets] Port '{self.port}' is already in use on this machine")
                        return

                self.sock.settimeout(1)
                self.sock.listen(10)
                self.listening = 1
                IRCD.configuration.our_ports.append(int(self.port))

                if output:
                    is_tls = "tls" in self.options
                    client_type = "servers" if "servers" in self.options else "clients"
                    logging.info(f"Listening on {self.ip}:{self.port} :: {'TLS' if is_tls else 'unsecure'} ({client_type})")

                IRCD.selector.register(self.sock, selectors.EVENT_READ, data=self)

        except Exception as ex:
            logging.exception(ex)

    def stop_listening(self):
        try:
            IRCD.selector.unregister(self.sock)
        except KeyError:
            pass
        self.listening = 0
        try:
            if isinstance(self.sock, OpenSSL.SSL.Connection):
                self.sock.shutdown()
            else:
                self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            self.sock.close()
        except Exception as ex:
            logging.exception(ex)

        self.sock.close()
        logging.info(f"Stopped listening on port: {self.port}")

    def verify_option(self, option):
        if option == "tls":
            self.tls = 1
            if not self.cert:
                self.cert = IRCD.rootdir + "/tls/server.cert.pem"
            if not self.key:
                self.key = IRCD.rootdir + "/tls/server.key.pem"

        self.options.append(option)

    def fileno(self):
        return self.sock.fileno()

    def __repr__(self):
        return f"<Listen '{self.ip}:{self.port}. Listening: {self.listening}', Sock: '{self.sock}'>"


class Spamfilter:
    entry_num = 0

    def __init__(self, match_type, action, duration, match, target, reason, conf_file, conf=1):
        self.match_type = match_type
        self.action = action
        self.duration = duration  # 1m, 1d etc.
        self.match = match
        self.target = target
        self.reason = reason
        self.conf = conf
        self.set_time = int(time.time())
        self.set_by = None
        self.entry_num = Spamfilter.entry_num
        self.conf_file = conf_file
        Spamfilter.entry_num += 1
        IRCD.configuration.spamfilters.append(self)

    def active_time(self):
        return int(time.time()) - self.set_time

    def __repr__(self):
        return f"<Spamfilter '{self.match} -> {self.reason}'>"


class Operclass:
    def __init__(self, name, permissions: list):
        self.name = name
        self.parent = None
        self.permissions = permissions
        IRCD.configuration.operclasses.append(self)

    def has_permission(self, check_path: str) -> int:
        """
        Check if the user has the specified permission.

        :param check_path: Permission path to check, e.g. "channel:override:invite"
        :return: 1 if user has permission, 0 otherwise
        """

        permissions = self.permissions
        if self.parent:
            parent_permissions = [o.permissions for o in IRCD.configuration.operclasses if o.name == self.parent]
            permissions.extend(p for p in parent_permissions if p not in permissions)

        path_parts = check_path.split(':')

        for perm_list in permissions:
            perm_index = path_index = 0
            while perm_index < len(perm_list):
                if path_index < len(path_parts) and path_parts[path_index] == perm_list[perm_index]:
                    if perm_index == len(perm_list) - 1:
                        return 1
                    if path_index == len(path_parts) - 1:
                        break
                    path_index += 1
                perm_index += 1

        return 0

    def __repr__(self):
        return f"<Operclass '{self.name}'>"


class Oper:
    def __init__(self, name, connectclass, operclass, password, mask: Mask):
        self.name = name
        self.connectclass = connectclass
        self.operclass = operclass
        self.password = password
        self.host = []
        self.mask = mask
        self.modes = ''
        self.snomasks = ''
        self.operhost = ''
        self.ignore = []
        self.requiredmodes = ''
        self.swhois = None
        IRCD.configuration.opers.append(self)

    def __repr__(self):
        return f"<Oper '{self.name}:{self.operclass}'>"


class Link:
    def __init__(self, name, password, connectclass, incoming_mask: Mask):
        self.name = name
        self.password = password  # Deprecated. Use `auth` instead.
        self.connectclass = connectclass
        self.incoming_mask = incoming_mask
        self.auth = {}
        self.incoming = {}
        self.outgoing = {}
        self.options = []
        self.outgoing_options = []
        self.last_connect_attempt = int(time.time()) + IRCD.get_random_interval(max=60)
        self.fingerprint = None
        self.auto_connect = 0
        IRCD.configuration.links.append(self)

    def __repr__(self):
        return f"<Link '{self.name}'>"


class Require:
    def __init__(self, what, mask: Mask, reason):
        self.what = what
        self.mask = mask
        self.reason = reason
        IRCD.configuration.requires.append(self)

    def __repr__(self):
        return f"<Require '{self.what}' {self.mask} -> {self.reason}>"


class Alias:
    def __init__(self, name, _type):
        self.name = name
        self.type = _type
        self.target = name
        self.spamfilter = 0
        self.target = None
        self.options = []
        IRCD.configuration.aliases.append(self)

    def __repr__(self):
        return f"<Alias '{self.name}' -> '{self.target}'>"


class Except:
    def __init__(self, name, mask: Mask, comment='*', types=None):
        if types is None:
            types = []
        self.name = name
        self.mask = mask
        self.comment = comment
        self.set_time = 0
        self.expire = 0
        self.types = types
        IRCD.configuration.excepts.append(self)

    def __repr__(self):
        return f"<Except '{self.name} -> {self.mask}'>"


class Ban:
    def __init__(self, ban_type, mask: Mask, reason):
        self.type = ban_type
        self.mask = mask
        self.reason = reason
        IRCD.configuration.bans.append(self)

    def __repr__(self):
        return f"<Ban '{self.type} -> {self.mask}' -> '{self.reason}'>"


class Module:
    def __init__(self, name: str, module: object):
        self.name = name  # Package name, like modules.m_oper
        self.module = module  # Actual module object. Will be assigned upon load()
        self.errors = []
        self.header = {}
        IRCD.configuration.modules.append(self)

    def load(self, reload=False):
        if reload and self.module:
            try:
                self.module = importlib.reload(self.module)
                logging.debug(f"Reloaded: {self.name}")
            except Exception as ex:
                err_string = f"Unable to reload '{self.name}': {ex}"
                return err_string

        else:
            try:
                self.module = importlib.import_module(self.name)
            except ModuleNotFoundError as ex:
                logging.exception(ex)
                err_string = f"Error loading module '{self.name}': {ex}"
                return err_string
            try:
                importlib.reload(self.module)
            except ImportError as ex:
                logging.exception(ex)
                err_string = f"Unable to reload '{self.name}': {ex}"
                return err_string

        if hasattr(self.module, "init"):
            try:
                self.module.init(self)
            except Exception as ex:
                logging.exception(ex)
                err_string = f"Unable to load '{self.module.__name__}': {ex}"
                self.errors.append(err_string)
                return err_string
        if hasattr(self.module, "HEADER"):
            self.header = self.module.HEADER

        if self.errors:
            for error in self.errors:
                logging.error(error)

    def post_load(self):
        """ This will be called after all modules are initialised. """
        if hasattr(self.module, "post_load"):
            self.module.post_load(self)

    def __repr__(self):
        return f"<Module '{self.name}'>"
