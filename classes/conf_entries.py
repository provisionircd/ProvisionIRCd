import threading
import time
import socket
import importlib

import OpenSSL.SSL

from handle.core import IRCD
from handle.functions import logging
from handle.handle_tls import create_ctx, wrap_socket
import select


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
    def __init__(self, mask, class_obj, maxperip):
        self.mask = mask
        self.class_obj = class_obj
        self.maxperip = int(maxperip)
        self.options = []
        self.block = None
        self.password = None
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
                self.sock = wrap_socket(self)
                self.sock.set_accept_state()

            if not self.listening:
                ip = "" if self.ip == '*' else self.ip
                self.sock.bind((ip, int(self.port)))
                self.sock.listen(10)
                self.listening = 1
                IRCD.configuration.our_ports.append(int(self.port))
                if output:
                    logging.info(f'Listening on {self.ip}:{self.port} :: {"TLS" if "tls" in self.options else "insecure"} '
                                 f'({"servers" if "servers" in self.options else "clients"})')
                if IRCD.use_poll:
                    IRCD.poller.register(self.sock, select.POLLIN)
        except Exception as ex:
            logging.exception(ex)

    def stop_listening(self):
        if IRCD.use_poll:
            try:
                IRCD.poller.unregister(self.sock)
            except KeyError:
                pass
        self.listening = 0
        try:
            if isinstance(self.sock, OpenSSL.SSL.Connection):
                self.sock.shutdown()
            else:
                self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
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
        :param check_path:          Example: channel:override:invite
        :return:                    True or False
        """

        permissions = self.permissions
        if self.parent:
            parent_permissions = [o.permissions for o in IRCD.configuration.operclasses if o.name == self.parent]
            for perm_list in [p for p in parent_permissions if p not in permissions]:
                permissions.append(perm_list)

        for perm_list in permissions:
            path = check_path.split(':')
            while perm_list:
                current = path[0]
                if current == perm_list[0]:
                    if len(perm_list) == 1:
                        return 1
                    if len(path) == 1:
                        break
                    path = path[1:]
                perm_list = perm_list[1:]

        return 0

    def __repr__(self):
        return f"<Operclass '{self.name}'>"


class Oper:
    mask_types = ["certfp", "account", "ip"]

    def __init__(self, name, connectclass, operclass, password, mask):
        self.name = name
        self.connectclass = connectclass
        self.operclass = operclass
        self.password = password
        self.host = []
        self.mask = mask
        self.modes = ""
        self.snomasks = ""
        self.operhost = ""
        self.ignore = []
        self.requiredmodes = ""
        self.swhois = None
        IRCD.configuration.opers.append(self)
        for mask in self.mask:
            if mask[0] in Oper.mask_types:
                continue
            self.host.append(mask[0])

    @property
    def certfp_mask(self):
        certfp_mask = []
        for mask in [m for m in self.mask if m[0] == "certfp"]:
            certfp_mask.append(mask[1])
        return certfp_mask

    @property
    def account_mask(self):
        account_mask = []
        for mask in [m for m in self.mask if m[0] == "account"]:
            account_mask.append(mask[1])
        return account_mask

    @property
    def ip_mask(self):
        ip_mask = []
        for mask in [m for m in self.mask if m[0] == "ip"]:
            ip_mask.append(mask[1])
        return ip_mask

    def __repr__(self):
        return f"<Oper '{self.name}:{self.operclass}'>"


class Link:
    def __init__(self, name, password, connectclass):
        self.name = name
        self.password = password
        self.connectclass = connectclass
        self.incoming = {}
        self.outgoing = {}
        self.options = []
        self.outgoing_options = []
        self.incoming_mask = []
        self.last_connect_attempt = int(time.time()) + IRCD.get_random_interval()
        self.fingerprint = None
        self.auto_connect = 0
        IRCD.configuration.links.append(self)

    def __repr__(self):
        return f"<Link '{self.name}'>"


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
    mask_types = ["certfp", "account", "ip"]

    def __init__(self, name, mask, comment="*"):
        self.name = name
        self.mask = mask
        self.comment = comment
        self.set_time = 0
        self.expire = 0
        self.types = []
        IRCD.configuration.excepts.append(self)

    @property
    def certfp_mask(self):
        certfp_mask = []
        for mask in [m for m in self.mask if m[0] == "certfp"]:
            certfp_mask.append(mask[1])
        return certfp_mask

    @property
    def account_mask(self):
        account_mask = []
        for mask in [m for m in self.mask if m[0] == "account"]:
            account_mask.append(mask[1])
        return account_mask

    @property
    def ip_mask(self):
        ip_mask = []
        for mask in [m for m in self.mask if m[0] == "ip"]:
            ip_mask.append(mask[1])
        return ip_mask

    def __repr__(self):
        return f"<Except '{self.name} -> {self.mask}'>"


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
            except Exception as ex:
                err_string = f"Unable to reload '{self.module.__name__}': {ex}"
                self.errors.append(err_string)
                return err_string

        else:
            try:
                self.module = importlib.import_module(self.name)
            except ModuleNotFoundError as ex:
                logging.exception(ex)
                logging.error(f"Module {self.name} not found")
                return
            importlib.reload(self.module)
            # logging.debug(f"Loaded module: {self.name}")

        if hasattr(self.module, 'init'):
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
        """
        This will be called after all modules are initialised.
        """
        if hasattr(self.module, "post_load"):
            self.module.post_load(self)

    def __repr__(self):
        return f"<Module '{self.name}'>"
