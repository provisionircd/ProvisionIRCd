import os
import sys

from handle.logger import logging, IRCDLogger
from handle.core import IRCD, Usermode, Command, Snomask, Stat, init_core_classes
from handle.client import Server
from handle.channel import Channel
from classes.data import Isupport, Hook, Extban
from handle.configparser import ConfigParser
import handle.validate_conf
from modules.ircv3.messagetags import MessageTag

config_commands = {
    "me": handle.validate_conf.config_test_me,
    "admin": handle.validate_conf.config_test_admin,
    "settings": handle.validate_conf.config_test_settings,
    "class": handle.validate_conf.config_test_class,
    "allow": handle.validate_conf.config_test_allow,
    "listen": handle.validate_conf.config_test_listen,
    "spamfilter": handle.validate_conf.config_test_spamfilter,
    "operclass": handle.validate_conf.config_test_operclass,
    "link": handle.validate_conf.config_test_link,
    "oper": handle.validate_conf.config_test_oper,
    "alias": handle.validate_conf.config_test_alias,
    "except": handle.validate_conf.config_test_except,
    "ulines": handle.validate_conf.config_test_ulines,
    "ban": handle.validate_conf.config_test_bans,
    "require": handle.validate_conf.config_test_require
}


class ConfigBuild:
    init_core_classes()

    def __init__(self, conffile="ircd.conf", rehash=0, debug=0):
        path = os.path.dirname(os.path.abspath(os.path.join(os.path.abspath(__file__), "..")))
        os.chdir(path)
        IRCD.rootdir = path
        IRCD.confdir = f"{path}/conf/"
        IRCD.modules_dir = f"{path}/modules/"
        if debug:
            IRCDLogger.debug()
        IRCD.conf_file = conffile
        self.conf_path = f"{IRCD.rootdir}/conf/{conffile}"
        IRCD.conf_path = self.conf_path
        self.rehash = rehash
        self.current_conf = None

    def _save_last_config_state(self):
        from modules.ircv3.messagetags import MessageTag
        return dict(umodes=Usermode.table, cmodes=Channel.modes_table, hooks=Hook.hooks, extbans=Extban.table,
                    commands=Command.table, isupport=Isupport.table, mtags=MessageTag.table,
                    listen=IRCD.configuration.listen, conf=IRCD.configuration)

    def _reload_modules(self, rehash):
        for mod in IRCD.configuration.modules:
            if result := mod.load(reload=rehash):
                ConfigParser.error(result, showpath=0)

    def _reset_module_tables(self):
        Command.table = [cmd for cmd in Command.table if not cmd.module]
        Usermode.table = []
        Channel.modes_table = []
        Snomask.table = []
        Hook.hooks = {}
        Isupport.table = []
        Extban.table = []
        Stat.table = []
        MessageTag.table = []

    def _validate_config_entries(self):
        for block in IRCD.configuration.entries:
            if block.name in config_commands:
                config_commands[block.name](block)

        for mod in IRCD.configuration.modules:
            mod.post_load()

        for oper in IRCD.configuration.opers:
            if not IRCD.configuration.get_class(oper.connectclass):
                ConfigParser.errors.append(f"Given class for oper '{oper}' is not found: {oper.connectclass}")

        for link in IRCD.configuration.links:
            if not IRCD.configuration.get_class(link.connectclass):
                ConfigParser.errors.append(f"Given class for link '{link}' is not found: {link.connectclass}")

        for allow in IRCD.configuration.allow:
            if not IRCD.configuration.get_class(allow.connectclass_name):
                ConfigParser.errors.append(f"Given class for allow-block not found: {allow.connectclass_name}")

        for oper in IRCD.configuration.opers:
            if not (operclass := next((c for c in IRCD.configuration.operclasses if oper.operclass in [c, c.name]), 0)):
                ConfigParser.errors.append(f"Oper '{oper.name}' has oper-class assigned but it does not exist: {oper.operclass}")
            else:
                oper.operclass = operclass

    def _handle_listen_ports(self, last_listen, new_listen):
        IRCD.configuration.listen = []
        if last_listen:
            existing_ports = {listener.port for listener in IRCD.configuration.listen}
            unique_listeners = [lis for lis in last_listen if lis.port not in existing_ports]
            IRCD.configuration.listen.extend(unique_listeners)

        if new_listen:
            existing_ports = {listener.port for listener in IRCD.configuration.listen}
            unique_listeners = [lis for lis in new_listen if lis.port not in existing_ports]
            IRCD.configuration.listen.extend(unique_listeners)

        new_ports = {item.port for item in new_listen}
        listeners_to_remove = [lis for lis in last_listen if lis.port not in new_ports and lis.listening]
        for listener in listeners_to_remove:
            listener.stop_listening()
            if listener in IRCD.configuration.listen:
                IRCD.configuration.listen.remove(listener)
                if listener.port in IRCD.configuration.our_ports:
                    IRCD.configuration.our_ports.remove(int(listener.port))

        for listen in IRCD.configuration.listen:
            listen.start_listen()

    def _restore_config(self, last_state):
        """ Restore previous configuration after failed rehash. """
        Channel.modes_table = last_state["cmodes"]
        Usermode.table = last_state["umodes"]
        Hook.hooks = last_state["hooks"]
        Extban.table = last_state["extbans"]
        Command.table = last_state["commands"]
        Isupport.table = last_state["isupport"]
        MessageTag.table = last_state["mtags"]
        IRCD.configuration = last_state["conf"]
        logging.error("Rehashing failed; previous configuration restored.")

    def is_ok(self, rehash=0, rehash_client=None, reloadmods=0, cmd_rehash_errors=None):
        cmd_rehash_errors = cmd_rehash_errors or []
        if not rehash:
            IRCD.configuration = Configuration()
            IRCD.me = Server()
            IRCD.logger.view_logging_info()

        last_state = self._save_last_config_state()
        our_ports = IRCD.configuration.our_ports

        IRCD.configuration = Configuration()
        IRCD.configuration.our_ports = our_ports

        if reloadmods:
            self._reset_module_tables()

        conf_build = ConfigParser(conf_path=IRCD.conf_path)

        required_blocks = ["me", "allow", "listen", "class", "settings"]
        if missing := set(required_blocks).difference(set(conf_build.cache)):
            for m in missing:
                ConfigParser.error(f"{m} {{ }} block missing in configuration", showpath=0)

        if reloadmods or not rehash:
            self._reload_modules(rehash)

        if not ConfigParser.errors and not handle.validate_conf.ConfErrors.entries:
            self._validate_config_entries()

        if handle.validate_conf.ConfWarnings.entries:
            for warning in handle.validate_conf.ConfWarnings.entries:
                logging.warning(warning)

        if ConfigParser.errors or handle.validate_conf.ConfErrors.entries:
            for error in ConfigParser.errors + handle.validate_conf.ConfErrors.entries:
                logging.error(error)
                cmd_rehash_errors.append(error)
                if rehash_client:
                    IRCD.server_notice(rehash_client, data=f"*** [error] -- {error}")

            # Exit if not rehashing, otherwise restore previous config.
            if not rehash:
                exit()

            ConfigParser.errors = []
            handle.validate_conf.ConfErrors.entries = []
            self._restore_config(last_state)
            return 0

        logging.info("Configuration ok.")
        self._handle_listen_ports(last_state["listen"], IRCD.configuration.listen)
        return 1


class Configuration:
    def __init__(self):
        self.entries = []
        self.settings = {}
        self.modules = []
        self.opers = []
        self.operclasses = []
        self.listen = []
        self.our_ports = []
        self.vhost = []
        self.allow = []
        self.spamfilters = []
        self.excepts = []
        self.bans = []
        self.connectclass = []
        self.links = []
        self.aliases = []
        self.requires = []
        self.conf_file = ''

    @staticmethod
    def get_blocks(blockname):
        return [b for b in IRCD.configuration.entries if b.name == blockname]

    @staticmethod
    def get_block(blockname):
        return next((b for b in IRCD.configuration.entries if b.name == blockname), 0)

    @staticmethod
    def get_items(path):
        if len(path_split := path.split(':')) < 2:
            return

        block_name, block_path = path_split[0], path_split[1:]
        for block in IRCD.configuration.get_blocks(block_name):
            if items := block.get_items(':'.join(block_path)):
                return items

    @staticmethod
    def setting_empty(key):
        return key not in IRCD.configuration.settings

    @staticmethod
    def get_oper(name):
        return next((o for o in IRCD.configuration.opers if o.name == name), 0)

    @staticmethod
    def get_class(name):
        return next((c for c in IRCD.configuration.connectclass if c.name == name), 0)

    @staticmethod
    def get_listen_by_port(port):
        if not port.isdigit():
            return 0
        return next((listen for listen in IRCD.configuration.listen if int(listen.port) == int(port)), 0)
