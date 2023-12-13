import os
import sys
import select

from handle.logger import logging, IRCDLogger
from handle.core import Channelmode, Usermode, IRCD, Command, Configuration, Extban, Isupport, Snomask, Stat, Hook, MessageTag
from handle.validate_conf import (
    ConfErrors,
    load_module,
    config_test_me,
    config_test_admin,
    config_test_settings,
    config_test_class,
    config_test_allow,
    config_test_listen,
    config_test_spamfilter,
    config_test_operclass,
    config_test_link,
    config_test_oper,
    config_test_alias,
    config_test_except,
    config_test_ulines
)

config_commands = {
    "me": config_test_me,
    "admin": config_test_admin,
    "settings": config_test_settings,
    "class": config_test_class,
    "allow": config_test_allow,
    "listen": config_test_listen,
    "spamfilter": config_test_spamfilter,
    "operclass": config_test_operclass,
    "link": config_test_link,
    "oper": config_test_oper,
    "alias": config_test_alias,
    "except": config_test_except,
    "ulines": config_test_ulines

}

path = os.path.abspath(__file__)
path = os.path.abspath(os.path.join(path, ".."))
dir_path = os.path.dirname(path)
os.chdir(dir_path)

IRCD.rootdir = dir_path
IRCD.confdir = dir_path + '/conf/'
IRCD.modules_dir = dir_path + '/modules/'

# Enable this to display configuration parse debug output.
debug = 0


class ConfigBuild:
    def __init__(self, conffile="ircd.conf", rehash=0, debug=0):
        if debug:
            IRCDLogger.debug()
        IRCD.conf_file = conffile
        self.conf_path = IRCD.rootdir + f"/conf/{conffile}"
        IRCD.conf_path = self.conf_path
        Configuration.conf_file = IRCD.conf_file
        self.rehash = rehash
        self.current_conf = None

    def is_ok(self, rehash=0, rehash_client=None, reloadmods=0):
        if not rehash:
            if IRCD.use_poll:
                if sys.platform.startswith("win32"):
                    logging.warning("Windows does not support select.poll(), using select.select() instead.")
                    IRCD.use_poll = 0
                else:
                    IRCD.poller = select.poll()

        # Save last configuration stae.
        # In the event of a rehash, and it fails, we just assign everything back to the previous state.
        last_umodes = Usermode.table
        last_cmodes = Channelmode.table
        last_hooks = Hook.hooks
        last_extbans = Extban.table
        last_commands = Command.table
        last_isupport = Isupport.table
        last_mtags = MessageTag.table
        last_listen = IRCD.configuration.listen
        our_ports = IRCD.configuration.our_ports
        last_conf = None
        if rehash:
            last_conf = IRCD.configuration

        IRCD.configuration = Configuration()
        IRCD.configuration.our_ports = our_ports

        if reloadmods:
            """ Only remove non-core commands. """
            Command.table = [cmd for cmd in Command.table if not cmd.module]
            Usermode.table = []
            Channelmode.table = []
            Snomask.table = []
            Hook.hooks = {}
            Isupport.table = []
            Extban.table = []
            Stat.table = []
            MessageTag.table = []

        # Parse all config files and assign it to a variable. Used to check for missing blocks.
        conf_build = ConfigParser(conf_path=IRCD.conf_path)

        """ Check for missing required blocks first. """
        required_blocks = ["me", "allow", "listen", "class", "settings"]
        missing_blocks = set(required_blocks).difference(set(conf_build.cache))
        for m in missing_blocks:
            ConfigParser.error(f"{m} {{ }} block missing in configuration", showpath=0)

        if reloadmods or not rehash:
            """ Don't reload modules on rehash by default. """
            for mod in IRCD.configuration.modules:
                result = mod.load(reload=rehash)
                if result:
                    ConfigParser.error(result, showpath=0)

        """
        If the configuration file does not contain any errors,
        we can now validate all conf data and load modules. 
        """
        if not ConfigParser.errors and not ConfErrors.entries:
            for block in IRCD.configuration.entries:
                if block.name in config_commands:
                    func = config_commands[block.name]
                    func(block)

            for mod in IRCD.configuration.modules:
                mod.post_load()

            for oper in IRCD.configuration.opers:
                if not IRCD.configuration.get_class(oper.connectclass):
                    ConfigParser.errors.append(f"Given class for oper '{oper}' is not found: {oper.connectclass}")

            for link in IRCD.configuration.links:
                if not IRCD.configuration.get_class(link.connectclass):
                    ConfigParser.errors.append(f"Given class for link '{link}' is not found: {link.connectclass}")

            # Check if operclasses in operblocks actually exist.
            for oper in IRCD.configuration.opers:
                if not (operclass := next((c for c in IRCD.configuration.operclasses if oper.operclass in [c, c.name]), 0)):
                    ConfigParser.errors.append(f"Oper '{oper.name}' has oper-class assigned but it does not exist: {oper.operclass}")
                else:
                    oper.operclass = operclass

        if ConfigParser.errors or ConfErrors.entries:
            for error in ConfigParser.errors + ConfErrors.entries:
                logging.error(error)
                if rehash_client:
                    IRCD.server_notice(rehash_client, data=f"*** [error] -- {error}")
            # If it's not a rehash, we can safely exit.
            if not rehash:
                exit()

            ConfigParser.errors = []
            ConfErrors.entries = []

            # It was a rehash, but it failed, restoring previously valid configuration.
            Channelmode.table = last_cmodes
            Usermode.table = last_umodes
            Hook.hooks = last_hooks
            Extban.table = last_extbans
            Command.table = last_commands
            Isupport.table = last_isupport
            MessageTag.table = last_mtags
            logging.error(f"Rehashing failed; previous configuration restored.")
            IRCD.configuration = last_conf
            return 0

        new_listen = IRCD.configuration.listen
        if last_listen:
            IRCD.configuration.listen = []
            for listen in [lis for lis in last_listen if lis.port not in [lis.port for lis in IRCD.configuration.listen]]:
                IRCD.configuration.listen.append(listen)

        if new_listen:
            for listen in [lis for lis in new_listen if lis.port not in [lis.port for lis in IRCD.configuration.listen]]:
                IRCD.configuration.listen.append(listen)

        # Check if there are any ports in last_listen that are not in new_listen, and close them.
        for listen in [lis for lis in last_listen if lis.port not in [lis.port for lis in new_listen] and lis.listening]:
            listen.stop_listening()
            if listen in IRCD.configuration.listen:
                IRCD.configuration.listen.remove(listen)
                if listen.port in IRCD.configuration.our_ports:
                    IRCD.configuration.our_ports.remove(int(listen.port))

        for listen in IRCD.configuration.listen:
            listen.start_listen()

        logging.info(f"Configuration ok.")
        return 1


class ConfigBlock:
    def __init__(self, filename, linenumber, name, value=None):
        self.name = name
        self.value = value
        self.filename = filename
        self.linenumber = linenumber
        self.entries = []
        IRCD.configuration.entries.append(self)

    def get_single_value(self, path):
        for item in self.entries:
            ps = path.split(':')
            for entry in item.path:
                if not ps:
                    entry = entry.encode().decode("unicode_escape")
                    return entry
                if entry == ps[0]:
                    ps = ps[1:]

    def get_path(self, path):
        entries = self.entries.copy()
        blocks = Configuration.get_blocks(self.name)
        for block in blocks:
            for entry in block.entries:
                if entry not in entries:
                    entries.append(entry)

        result = []
        for item in entries:
            ps = path.split(':')
            for entry in item.path:
                if not ps:
                    result.append(entry)
                    break
                if entry == ps[0]:
                    ps = ps[1:]
        return result

    def get_item(self, itemname):
        entries = []
        for entry in [e for e in self.entries if e not in entries]:
            entries.append(entry)

        result = next((i for i in self.entries if i.get_path(itemname)), 0)
        return result

    def get_items(self, itemname=''):
        if not itemname:
            return [i for i in self.entries]
        return [i for i in self.entries if i.get_path(itemname)]

    def get_all_entries(self):
        entries = self.entries.copy()
        blocks = Configuration.get_blocks(self.name)
        for block in blocks:
            for entry in [entry for entry in block.entries if entry not in entries]:
                entries.append(entry)
        return entries

    def get_list_from_path(self, path=''):
        result = []
        ps = path.split(':')
        for match in self.get_items(path):
            path_idx = 0
            for entry_item in match.path:
                if not path:
                    result.append(entry_item)
                    continue
                current_path = ps[path_idx]
                if entry_item == current_path:
                    path_idx += 1
                    if path_idx == len(ps):
                        result.append(' '.join(match.path[path_idx:]))
                        path_idx = 0
                        continue

        return result

    def __str__(self):
        return f"<ConfigBlock '{self.name}'>"


class ConfigBlockEntry:
    def __init__(self, block: ConfigBlock, path, filename, linenumber):
        self.path = path
        self.filename = filename
        self.linenumber = linenumber
        self.block = block
        self.block.entries.append(self)

    def get_single_value(self, path=None):
        if not path:
            return self.path[0]

        ps = path.split(':')
        for entry in self.path:
            if not ps:
                return entry
            if entry == ps[0]:
                ps = ps[1:]

    def get_path(self, path):
        result = []
        ps = path.split(':')
        for entry in self.path:
            if not ps:
                result.append(entry)
                break
            if entry == ps[0]:
                ps = ps[1:]
        return result

    def __str__(self):
        return f"<ConfigBlockItem 'Block: {self.block.name}', File: '{self.filename}', Line: '{self.linenumber}', Path: '{self.path}'>"


class ConfigParser:
    errors = []
    current_path = None
    current_line = None
    line_warnings = []

    def __init__(self, conf_path):  # =IRCD.rootdir + "/conf/ircd.conf"):
        self.cache = {}
        # Keeps track of current conf depth and line numbers.
        # Main conf first.
        rel_path = os.path.relpath(conf_path)
        self.subconfs = {rel_path: 1}
        self.init_vars()
        self.conf_path = conf_path
        if not os.path.isfile(self.conf_path):
            logging.error(f"Could not find main configuration file {self.conf_path}")
            logging.error("You can find example configuration files in the conf/examples directory.")
            logging.error("Copy conf/examples/ircd.example.conf to the conf/ directory, rename it to ircd.conf and edit the file, then run ProvisionIRCd again.")
            if not IRCD.running:
                exit()
        with open(self.conf_path) as self.file_obj:
            self.conf_content = self.file_obj.read()
        self.cursor = -1
        self.prev_config_block = None
        self.valid_directives = ["module", "include"]
        self.parse(self.conf_content)

    def init_vars(self):
        self.READING_BLOCK_NAME = True
        self.BLOCK_NAME = ""
        self.BLOCK_VALUE = ""  # Not all blocks have values.
        self.single_line_comment_check = False
        self.single_line_comment = False
        self.multi_line_comment_check = False
        self.multi_line_comment = False
        self.multi_line_comment_check_for_end = False
        self.in_quoted_string = False
        self.opening_count = 0
        self.closing_count = 0
        self.got_bracket_data = 0
        self.semicolon = 0
        self.bracket_warn = 0
        if debug:
            logging.debug("Parser reset: block end")

        self.directive_tree = []

        self.capture_data = True
        self.data_captured = ""

        self.config_block = None

    @property
    def in_comment(self):
        return self.single_line_comment or self.multi_line_comment

    @staticmethod
    def error(errmsg, showpath=1, line=0):
        if not line:
            line = str(ConfigParser.current_line)
        path = f"{ConfigParser.current_path if showpath else ''}:{line}"
        if path in ConfigParser.line_warnings:
            return
        ConfigParser.line_warnings.append(path)
        path = ''
        if showpath:
            path = f"{ConfigParser.current_path}:{line}: "
        errmsg = path + errmsg
        if errmsg not in ConfigParser.errors:
            ConfigParser.errors.append(errmsg)

    def parse(self, content):
        for self.cursor, char in enumerate(content, start=0):
            self.current_conf = list(self.subconfs)[-1]
            ConfigParser.current_path = list(self.subconfs)[-1]
            ConfigParser.current_conf = self.current_conf
            ConfigParser.current_line = self.subconfs[self.current_conf]
            char = content[self.cursor]
            self.prev_char = ''
            if self.cursor > 0:
                self.prev_char = content[self.cursor - 1]

            if char == '\n':
                if self.cursor + 1 == len(content):
                    if self.opening_count > self.closing_count:
                        errmsg = f"[1] Block starting on line {self.prev_config_block.linenumber} did not end properly. Check if you are missing a }}."
                        ConfigParser.error(errmsg, line=self.prev_config_block.linenumber)
                        self.bracket_warn = 1
                        continue
                    if self.opening_count < self.closing_count:
                        errmsg = f"[2] Block starting on line {self.prev_config_block.linenumber} ended unexpectedly. Check if you have a }} too many."
                        ConfigParser.error(errmsg, line=self.prev_config_block.linenumber)
                        self.bracket_warn = 1
                        continue
                if self.in_quoted_string:
                    ConfigParser.error(f"Quoted string not ended properly on line {ConfigParser.current_line}.")
                    break
                if self.data_captured.strip():
                    ConfigParser.error("missing semicolon")
                    self.data_captured = ''
                    break

                self.subconfs[self.current_conf] += 1
                if self.single_line_comment:
                    self.single_line_comment = 0
                    self.single_line_comment_check = 0
                    if debug:
                        logging.debug(f"Newline found, ending single_line_comment")

            # if char == ':' and not self.in_quoted_string and not self.in_comment:
            #     ConfigParser.error(f"Colon on line {ConfigParser.current_line} must be enclosed in quotes.")
            #     continue

            if char == '"':
                if self.prev_char != '\\':
                    self.in_quoted_string = 0 if self.in_quoted_string else 1
                else:
                    self.read_data(char)
                    continue

            if self.multi_line_comment_check_for_end and char != "/":
                self.multi_line_comment_check_for_end = 0
            if self.multi_line_comment_check and char != "*":
                self.multi_line_comment_check = 0
                if debug:
                    logging.debug(f"Multi-line comment cancelled: char was {char}")

            if char == "#":
                if not self.in_quoted_string and not self.single_line_comment:
                    if debug:
                        logging.debug("Found #, don't process anything until newline.")
                    self.single_line_comment = 1
                    continue

            if self.prev_char == "/" and not self.in_quoted_string and not self.in_comment:
                if char not in ['/', '*', '\n']:
                    self.single_line_comment_check = 0
                    self.multi_line_comment_check = 0
                    self.read_data(self.prev_char + char)
                    continue

            if char == "/":
                if self.in_quoted_string and not self.in_comment:
                    self.read_data(char)
                    continue
                if not self.single_line_comment and not self.in_quoted_string:
                    if self.single_line_comment_check:
                        if debug:
                            logging.debug("Second forward slash found, don't process anything until newline.")
                        self.single_line_comment = 1
                        self.single_line_comment_check = 0
                    if self.multi_line_comment_check_for_end:
                        self.multi_line_comment = 0
                        if debug:
                            logging.debug("Multi-line comment ended.")
                            logging.debug(f"Block name: {self.BLOCK_NAME}")
                        self.data_captured = ""
                        self.multi_line_comment_check_for_end = 0
                        continue
                    if not self.multi_line_comment:
                        self.single_line_comment_check = 1
                    if not self.single_line_comment and not self.multi_line_comment:
                        self.multi_line_comment_check = 1
                    continue

            if char == "*":
                if self.in_quoted_string and not self.in_comment:
                    self.read_data(char)
                    continue
                if self.multi_line_comment_check:
                    if debug:
                        logging.debug("Found a multi-line comment, don't process anything until we see */")
                    self.single_line_comment_check = 0
                    self.multi_line_comment_check = 0
                    self.multi_line_comment = 1
                elif self.multi_line_comment:
                    # End multi-line comment if next char is /
                    self.multi_line_comment_check_for_end = 1
                    if debug:
                        logging.debug("Possible end of multi-line comment incoming.")
            if self.in_comment:
                continue

            elif char == "{":
                if self.in_quoted_string:
                    self.read_data(char)
                    continue
                self.got_bracket_data = 0
                self.opening_count += 1
                # self.bracket_warn = 0
                if self.opening_count == 1:
                    self.BLOCK_NAME = self.BLOCK_NAME.strip()
                    if " " in self.BLOCK_NAME:
                        if len(self.BLOCK_NAME.split(' ')) != 2:
                            break

                        self.BLOCK_NAME, self.BLOCK_VALUE = self.BLOCK_NAME.split(" ")
                    self.config_block = ConfigBlock(filename=self.current_conf, linenumber=self.current_line, name=self.BLOCK_NAME, value=self.BLOCK_VALUE)
                    self.prev_config_block = self.config_block
                    if debug:
                        logging.debug(f"[o-cur] Set block-name: {self.BLOCK_NAME}")
                        logging.debug(f"[o-cur] Set block-value (if any): {self.BLOCK_VALUE}")
                    self.cache[self.BLOCK_NAME] = {}
                    self.done_reading_block_name()

                if self.opening_count > 1:
                    self.data_captured = self.data_captured.strip()
                    if not self.data_captured:
                        errmsg = f"Invalid data on line {self.current_line}"
                        ConfigParser.error(errmsg)
                        continue
                    if debug:
                        logging.debug(f"[{{] Captured data: {self.data_captured}")
                    directive = self.data_captured
                    self.directive_tree.append(directive)
                    if debug:
                        logging.debug(f"[{{] Entered directive: {directive}")
                    tree = "->".join(self.directive_tree)
                    if debug:
                        logging.debug(f"[{{] Directive tree: {tree}")

                    self.data_captured = ""

            if char == "}":
                if self.in_quoted_string:
                    self.read_data(char)
                    continue

                # We exited a directive. Now we can read for new directive.
                if self.directive_tree:
                    directive = self.directive_tree[-1]
                    if debug:
                        logging.debug(f"[c-cur] Exiting directive: {directive}")
                    del self.directive_tree[-1]
                    tree = "->".join(self.directive_tree)
                    if debug:
                        logging.debug(f"[c-cur] Tree directive: {tree}")
                else:
                    if debug:
                        logging.debug(f"We are currently in the root block.")
                self.closing_count += 1

                if self.closing_count > self.opening_count:
                    errmsg = f"[3] Block starting on line {self.prev_config_block.linenumber} ended unexpectedly. Check if you have a }} too many."
                    ConfigParser.error(errmsg, line=self.prev_config_block.linenumber)
                    self.bracket_warn = 1
                    break

                if self.opening_count > self.closing_count:
                    if not self.got_bracket_data and not self.data_captured.strip() and not self.bracket_warn:
                        errmsg = f"Missing data between brackets"
                        ConfigParser.error(errmsg)
                        self.bracket_warn = 1
                        break

                if self.data_captured.strip():
                    ConfigParser.error(f"Data ended abruptly. Missing semicolon on line {self.current_line}?")
                    continue

                if self.opening_count == self.closing_count:
                    if not self.semicolon or not self.got_bracket_data:
                        errmsg = f"Invalid data between brackets. Missing data or missing semicolon."
                        ConfigParser.error(errmsg)
                    if not self.BLOCK_NAME.strip():
                        errmsg = f"Block started not line {self.current_line} does not have a name."
                        ConfigParser.error(errmsg)

                    self.init_vars()

            elif char == ";":
                if self.in_quoted_string:
                    self.read_data(char)
                    continue
                if self.data_captured.strip():
                    self.got_bracket_data = 1
                self.semicolon += 1
                if debug:
                    logging.warning(f"[;] Directive_tree on line {ConfigParser.current_line}: {self.directive_tree}")
                    logging.debug(f"Semicolon, reading block name? :: {self.READING_BLOCK_NAME}")
                self.data_captured = self.data_captured.strip()
                if not self.data_captured:
                    # errmsg = "No data found after semicolon. Check if there is data between brackets, or if you have a ; too many."
                    # ConfigParser.error(errmsg)
                    continue

                if not self.READING_BLOCK_NAME and self.config_block:
                    path = []
                    if self.BLOCK_VALUE:
                        path.append(self.BLOCK_VALUE)
                    for entry in self.directive_tree:
                        path.append(entry)

                    single_string_value = []
                    for entry in self.data_captured.split():
                        if [entry[0], entry[-1]] == ['"', '"']:
                            temp = entry.removeprefix('"').removesuffix('"')
                            path.append(temp)
                            continue
                        if entry.startswith('"'):
                            temp = entry.removeprefix('"')
                            single_string_value.append(temp)
                            continue
                        if entry.endswith('"'):
                            single_string_value.append(entry.removesuffix('"'))
                            path.append(' '.join(single_string_value))
                            single_string_value = []
                            continue
                        if single_string_value:
                            single_string_value.append(entry)
                            continue
                        path.append(entry)
                    if self.config_block:
                        ConfigBlockEntry(block=self.config_block, path=path, filename=self.current_conf, linenumber=self.current_line)

                if self.READING_BLOCK_NAME:  # Probably a keyword.
                    if len(self.data_captured.split(" ")) < 2:
                        directive, value = self.data_captured, None
                    else:
                        directive, value = self.data_captured.split(" ")
                    if directive not in self.valid_directives:
                        errmsg = f"Unknown directive: {directive}"
                        ConfigParser.error(errmsg)
                        self.data_captured = ''
                        continue
                    elif not value:
                        errmsg = f"Directive '{directive}' without filename"
                        ConfigParser.error(errmsg)
                        self.data_captured = ''
                        continue

                    self.data_captured = ""
                    if directive == "include":
                        self.include_conf(value)
                        continue
                    elif directive == "module":
                        value = value.removeprefix('"')
                        value = value.removesuffix('"')
                        if not os.path.isfile(IRCD.modules_dir + '/' + value + '.py'):
                            errmsg = f"Unable to find module: {value}"
                            ConfigParser.error(errmsg)
                            continue
                        load_module(value)
                        self.init_vars()
                        continue

                    continue

                self.data_captured = ""

            # Do not include {, } and ;.
            if char not in ['\n', '{', '}', ';']:
                self.read_data(char)

            continue

    def done_reading_block_name(self):
        if debug:
            logging.debug(f"We were reading block-name, but we are done now.")
        self.READING_BLOCK_NAME = False
        if debug:
            logging.debug(f"BLOCK_NAME: {self.BLOCK_NAME}")
        if self.BLOCK_NAME not in self.cache:
            self.cache[self.BLOCK_NAME] = {}
        if self.BLOCK_VALUE and self.BLOCK_VALUE not in self.cache[self.BLOCK_NAME]:
            self.cache[self.BLOCK_NAME][self.BLOCK_VALUE] = {}
        self.data_captured = ""

    def read_data(self, char):
        if self.capture_data:
            self.data_captured += char

        if self.READING_BLOCK_NAME:
            self.BLOCK_NAME += char

        if self.opening_count == 1 and char.strip():
            self.got_bracket_data = 1

    def include_conf(self, module):
        self.BLOCK_NAME = ""
        module = module.removeprefix('"')
        module = module.removesuffix('"')
        if debug:
            logging.debug(f"Parsing conf: {module}")

        load_file = IRCD.rootdir + "/conf/" + module

        if not os.path.isfile(load_file):
            ConfigParser.errors.append(f"Error on or around line {self.subconfs[self.current_conf]}: Could not find file: {load_file}")
            return

        with open(load_file) as f:
            self.original_content = self.conf_content
            self.original_cursor = self.cursor
            rel_path = os.path.relpath(load_file)
            self.subconfs[rel_path] = 1
            self.parse(f.read())

        del self.subconfs[self.current_conf]
        self.conf_content = self.original_content
        self.cursor = self.original_cursor
        self.init_vars()
