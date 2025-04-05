"""
ConfigBlock Methods
------------------

get_single_value(path: str) -> Any:
    Retrieves a single value from a configuration block matching the specified path.
    Example: me_block.get_single_value("server")  # Returns "irc.someserver.net"

get_path(path: str) -> list:
    Gets all values from entries matching the specified path.
    Example: me_block.get_path("name")  # Returns ["Example Server"]

get_item(itemname: str) -> ConfigBlockEntry:
    Gets the first ConfigBlockEntry matching the specified item name.
    Example: me_block.get_item("server")  # Returns ConfigBlockEntry for "server"

get_items(itemname: str = '') -> list:
    Gets all ConfigBlockEntry objects matching the specified item name.
    Example: listen_block.get_items("options:tls")  # Returns all TLS option entries

get_all_entries() -> list:
    Gets all entries from this block and all other blocks with the same name.
    Example: listen_block.get_all_entries()  # Returns all entries across all listen blocks

get_list_from_path(path: str = '') -> list:
    Gets a list of values from entries matching a path pattern.
    Example: spamfilter_block.get_list_from_path("target")  # Returns all target values


ConfigBlockEntry Methods
-----------------------

get_single_value(path: str = None) -> Any:
    Gets a single value from the entry's path.
    Example: entry.get_single_value()  # Returns the server value

get_path(path: str) -> list:
    Gets values from the entry matching the specified path.
    Example: entry.get_path("tls")  # Returns values under "options:tls"


Configuration Static Methods
---------------------------

get_blocks(blockname: str) -> list:
    Gets all blocks with a specific name.
    Example: Configuration.get_blocks("listen")  # Returns all listen blocks

get_block(blockname: str) -> ConfigBlock:
    Gets the first block with a specific name.
    Example: Configuration.get_block("me")  # Returns the "me" block

get_items(path: str) -> list:
    Gets all items matching a path pattern across all blocks.
    Example: Configuration.get_items("settings:cloak-key")  # Returns all cloak-key entries

setting_empty(key: str) -> int:
    Checks if a setting is empty or missing.
    Example: Configuration.setting_empty("cloak-key")  # Returns 0 if set

get_oper(name: str) -> Operator:
    Gets an operator by name.
    Example: Configuration.get_oper("admin")  # Returns the "admin" operator

get_class(name: str) -> Class:
    Gets a connection class by name.
    Example: Configuration.get_class("clients")  # Returns the "clients" class

get_listen_by_port(port: str) -> Listen:
    Gets a listen block by port number.
    Example: Configuration.get_listen_by_port("6667")  # Returns listen for port 6667


Source Information
-----------------

Each ConfigBlock and ConfigBlockEntry object contains:
- filename: Source file where the block/entry was defined
- linenumber: Line number where the block/entry was defined

Example:
    block = Configuration.get_block("me")
    print(f"Block defined in {block.filename}:{block.linenumber}")
"""

import os

from handle.core import IRCD

from handle.validate_conf import load_module
from handle.logger import logging

path = os.path.abspath(__file__)
path = os.path.abspath(os.path.join(path, ".."))
dir_path = os.path.dirname(path)
os.chdir(dir_path)


class ConfigParser:
    errors = []
    warnings = []
    current_path = None
    current_line = None
    line_warnings = set()

    def __init__(self, conf_path):
        self.READING_BLOCK_NAME: bool = True
        self.BLOCK_NAME: str = ''
        self.BLOCK_VALUE: str = ''
        self.single_line_comment_check: bool = False
        self.single_line_comment: bool = False
        self.multi_line_comment_check: bool = False
        self.multi_line_comment: bool = False
        self.multi_line_comment_check_for_end: bool = False
        self.in_quoted_string: bool = False
        self.got_bracket_data: int = 0
        self.bracket_warn: int = 0
        self.config_block: ConfigBlock | None = None
        self.prev_config_block = None

        self.conf_path = conf_path
        self.current_conf = None
        self.cursor = -1
        self.prev_char = ''
        self.data_captured: str = ''
        self.valid_directives = ["module", "include"]
        self.cache = {}
        self.subconfs = {}

        self._reset_parser_state()

        if not os.path.isfile(self.conf_path):
            logging.error(f"Could not find main configuration file {self.conf_path}")
            logging.error("You can find example configuration files in the conf/examples directory.")
            logging.error("Copy conf/examples/ircd.example.conf to the conf/ directory,"
                          "rename it to ircd.conf and edit the file, then run ProvisionIRCd again.")
            if not IRCD.running:
                exit()

        rel_path = os.path.relpath(conf_path)
        self.subconfs[rel_path] = 1

        with open(self.conf_path) as file_obj:
            self.parse(file_obj.read())

    def _reset_parser_state(self):
        self.READING_BLOCK_NAME: bool = True
        self.BLOCK_NAME: str = ''
        self.BLOCK_VALUE: str = ''
        self.single_line_comment_check: bool = False
        self.single_line_comment: bool = False
        self.multi_line_comment_check: bool = False
        self.multi_line_comment: bool = False
        self.multi_line_comment_check_for_end: bool = False
        self.in_quoted_string: bool = False
        self.opening_count: int = 0
        self.closing_count: int = 0
        self.got_bracket_data: int = 0
        self.semicolon: int = 0
        self.bracket_warn: int = 0
        self.directive_tree: list[str] = []
        self.data_captured: str = ''
        self.config_block: ConfigBlock | None = None

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

        ConfigParser.line_warnings.add(path)
        path_prefix = f"{ConfigParser.current_path}:{line}: " if showpath else ''
        errmsg = path_prefix + errmsg

        if errmsg not in ConfigParser.errors:
            ConfigParser.errors.append(errmsg)

    def parse(self, content):
        for self.cursor, char in enumerate(content):
            self.current_conf = list(self.subconfs)[-1]
            ConfigParser.current_path = list(self.subconfs)[-1]
            ConfigParser.current_line = self.subconfs[self.current_conf]

            char = content[self.cursor]
            self.prev_char = content[self.cursor - 1] if self.cursor > 0 else ''

            # Handle newlines (incrementing line counter, resetting comments)
            if char == '\n':
                if self.cursor + 1 == len(content) and self.opening_count > self.closing_count:
                    # Check for unclosed blocks at end of file
                    errmsg = (f"[1] Block starting on line {self.prev_config_block.linenumber} did not end properly. "
                              f"Check if you are missing a }}.")
                    ConfigParser.error(errmsg, line=self.prev_config_block.linenumber)
                    self.bracket_warn = 1
                    continue

                if self.cursor + 1 == len(content) and self.opening_count < self.closing_count:
                    # Check for unexpected block closures at end of file
                    errmsg = (f"[2] Block starting on line {self.prev_config_block.linenumber} ended unexpectedly. "
                              f"Check if you have a }} too many.")
                    ConfigParser.error(errmsg, line=self.prev_config_block.linenumber)
                    self.bracket_warn = 1
                    continue

                if self.in_quoted_string:
                    # Quoted string not properly terminated
                    ConfigParser.error(f"Quoted string not ended properly on line {ConfigParser.current_line}.")
                    break

                if self.data_captured.strip():
                    # Data without semicolon
                    ConfigParser.error("missing semicolon")
                    self.data_captured = ''
                    break

                # Increment line counter and reset single line comments
                self.subconfs[self.current_conf] += 1
                if self.single_line_comment:
                    self.single_line_comment = 0
                    self.single_line_comment_check = 0

            # Handle quoted strings
            if char == '"':
                if self.prev_char != '\\':
                    self.in_quoted_string = not self.in_quoted_string
                else:
                    self.read_data(char)
                    continue

            # Reset comment flags if not followed by expected characters
            if self.multi_line_comment_check_for_end and char != '/':
                self.multi_line_comment_check_for_end = 0

            if self.multi_line_comment_check and char != '*':
                self.multi_line_comment_check = 0

            # Handle single-line comments starting with #
            if char == '#':
                if not self.in_quoted_string and not self.single_line_comment:
                    self.single_line_comment = 1
                    continue

            # Handle forward slash for comments and escaped characters
            if self.prev_char == '/' and not self.in_quoted_string and not self.in_comment:
                if char not in ['/', '*', '\n']:
                    self.single_line_comment_check = 0
                    self.multi_line_comment_check = 0
                    self.read_data(self.prev_char + char)
                    continue

            if char == '/':
                if self.in_quoted_string and not self.in_comment:
                    self.read_data(char)
                    continue

                if not self.single_line_comment and not self.in_quoted_string:
                    # Handle single-line comment (//)
                    if self.single_line_comment_check:
                        self.single_line_comment = 1
                        self.single_line_comment_check = 0

                    # Handle end of multi-line comment (*/)
                    if self.multi_line_comment_check_for_end:
                        self.multi_line_comment = 0
                        self.data_captured = ''
                        self.multi_line_comment_check_for_end = 0
                        continue

                    # Set up for possible comment start
                    if not self.multi_line_comment:
                        self.single_line_comment_check = 1

                    if not self.single_line_comment and not self.multi_line_comment:
                        self.multi_line_comment_check = 1

                    continue

            # Handle asterisk for multi-line comments
            if char == '*':
                if self.in_quoted_string and not self.in_comment:
                    self.read_data(char)
                    continue

                if self.multi_line_comment_check:
                    # Start of multi-line comment (/*) detected
                    self.single_line_comment_check = 0
                    self.multi_line_comment_check = 0
                    self.multi_line_comment = 1
                elif self.multi_line_comment:
                    # Possible end of multi-line comment (*) detected
                    self.multi_line_comment_check_for_end = 1

            # Skip processing if in a comment
            if self.in_comment:
                continue

            # Handle opening curly brace for blocks
            elif char == '{':
                if self.in_quoted_string:
                    self.read_data(char)
                    continue

                # Check for syntax error: directive followed by block instead of semicolon
                if self.READING_BLOCK_NAME and self.BLOCK_NAME.strip():
                    block_name_parts = self.BLOCK_NAME.strip().split(' ', 1)
                    if block_name_parts and block_name_parts[0] in self.valid_directives:
                        errmsg = (f"Syntax error: directive '{block_name_parts[0]}' should be terminated with a semicolon, "
                                  f"not followed by a block")
                        ConfigParser.error(errmsg)
                        # We still increment opening_count to maintain the parse state balance

                self.got_bracket_data = 0
                self.opening_count += 1

                # Start of a new configuration block
                if self.opening_count == 1:
                    self.BLOCK_NAME = self.BLOCK_NAME.strip()

                    # Handle block name with optional value (e.g., "link server1")
                    if ' ' in self.BLOCK_NAME:
                        if block_parts := self.BLOCK_NAME.split(' ', 1):
                            self.BLOCK_NAME, self.BLOCK_VALUE = block_parts

                    # Create new config block
                    self.config_block = ConfigBlock(
                        filename=self.current_conf,
                        linenumber=self.current_line,
                        name=self.BLOCK_NAME,
                        value=self.BLOCK_VALUE
                    )
                    self.prev_config_block = self.config_block

                    # Add to cache for quick lookup
                    self.cache[self.BLOCK_NAME] = {}
                    self.done_reading_block_name()

                # Handle nested blocks (directives)
                if self.opening_count > 1:
                    # noinspection PyTypeChecker
                    self.data_captured = self.data_captured.strip()
                    if not self.data_captured:
                        errmsg = f"Invalid data on line {self.current_line}"
                        ConfigParser.error(errmsg)
                        continue

                    directive = self.data_captured
                    self.directive_tree.append(directive)
                    self.data_captured = ''

            # Handle closing curly brace for blocks
            if char == '}':
                if self.in_quoted_string:
                    self.read_data(char)
                    continue

                # Exit from current directive
                if self.directive_tree:
                    directive = self.directive_tree[-1]
                    del self.directive_tree[-1]

                self.closing_count += 1

                # Check for unbalanced braces
                if self.closing_count > self.opening_count:
                    errmsg = (f"[3] Block starting on line {self.prev_config_block.linenumber} ended unexpectedly. "
                              f"Check if you have a }} too many.")
                    ConfigParser.error(errmsg, line=self.prev_config_block.linenumber)
                    self.bracket_warn = 1
                    break

                # Check for empty blocks
                if self.opening_count > self.closing_count:
                    if not self.got_bracket_data and not self.data_captured.strip() and not self.bracket_warn:
                        errmsg = f"Missing data between brackets"
                        ConfigParser.error(errmsg)
                        self.bracket_warn = 1
                        break

                # Check for unclosed data
                if self.data_captured.strip():
                    ConfigParser.error(f"Data ended abruptly. Missing semicolon on line {self.current_line}?")
                    continue

                # End of block - validate and reset state
                if self.opening_count == self.closing_count:
                    if not self.semicolon or not self.got_bracket_data:
                        errmsg = f"Invalid data between brackets. Missing data or missing semicolon."
                        ConfigParser.error(errmsg)

                    if not self.BLOCK_NAME.strip():
                        errmsg = f"Block started on line {self.current_line} does not have a name."
                        ConfigParser.error(errmsg)

                    self._reset_parser_state()

            # Handle semicolon for statement termination
            elif char == ';':
                if self.in_quoted_string:
                    self.read_data(char)
                    continue

                if self.data_captured.strip():
                    self.got_bracket_data = 1

                self.semicolon += 1
                self.data_captured = self.data_captured.strip()

                if not self.data_captured:
                    continue

                # Process configuration item within a block
                if not self.READING_BLOCK_NAME and self.config_block:
                    path = []
                    if self.BLOCK_VALUE:
                        path.append(self.BLOCK_VALUE)

                    for entry in self.directive_tree:
                        path.append(entry)

                    # Parse data into components, handling quoted strings correctly
                    single_string_value = []
                    for entry in self.data_captured.split():
                        if entry.startswith('"') and entry.endswith('"') and len(entry) >= 2:
                            temp = entry[1:-1]
                            path.append(temp)
                            continue

                        if entry.startswith('"'):
                            temp = entry[1:]
                            single_string_value.append(temp)
                            continue

                        if entry.endswith('"'):
                            single_string_value.append(entry[:-1])
                            path.append(' '.join(single_string_value))
                            single_string_value = []
                            continue

                        if single_string_value:
                            single_string_value.append(entry)
                            continue

                        path.append(entry)

                    # Create a new configuration entry
                    if self.config_block:
                        ConfigBlockEntry(
                            block=self.config_block,
                            path=path,
                            filename=self.current_conf,
                            linenumber=self.current_line
                        )

                # Process directives in the root level
                if self.READING_BLOCK_NAME:
                    if len(self.data_captured.split(' ')) < 2:
                        directive, value = self.data_captured, None
                    else:
                        directive, value = self.data_captured.split(' ', 1)

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

                    self.data_captured = ''

                    # Handle include directive
                    if directive == "include":
                        self.include_conf(value)
                        continue
                    # Handle module directive
                    elif directive == "module":
                        value = value.strip('"')
                        if not os.path.isfile(IRCD.modules_dir + '/' + value + '.py'):
                            errmsg = f"Unable to find module: {value}"
                            ConfigParser.error(errmsg)
                            continue
                        load_module(value)
                        self._reset_parser_state()
                        continue

                    continue

                self.data_captured = ''

            if char not in ['\n', '{', '}', ';']:
                self.read_data(char)

    def done_reading_block_name(self):
        self.READING_BLOCK_NAME = False

        # Update cache for quick lookups
        if self.BLOCK_NAME not in self.cache:
            self.cache[self.BLOCK_NAME] = {}

        if self.BLOCK_VALUE and self.BLOCK_VALUE not in self.cache[self.BLOCK_NAME]:
            self.cache[self.BLOCK_NAME][self.BLOCK_VALUE] = {}

        self.data_captured = ''

    def read_data(self, char):
        self.data_captured += char

        if self.READING_BLOCK_NAME:
            self.BLOCK_NAME += char

        if self.opening_count == 1 and char.strip():
            self.got_bracket_data = 1

    def include_conf(self, module):
        self.BLOCK_NAME = ''
        module = module.strip('"')

        load_file = IRCD.rootdir + "/conf/" + module

        if not os.path.isfile(load_file):
            ConfigParser.errors.append(f"Error on or around line {self.subconfs[self.current_conf]}: Could not find file: {load_file}")
            return

        original_cursor = self.cursor

        # Set up new context for included file
        rel_path = os.path.relpath(load_file)
        self.subconfs[rel_path] = 1

        # Parse included file
        with open(load_file) as f:
            self.parse(f.read())

        # Restore previous context
        del self.subconfs[rel_path]
        self.cursor = original_cursor
        self._reset_parser_state()


class ConfigBlockEntry:
    def __init__(self, block, path, filename, linenumber):
        self.path = path
        self.filename = filename
        self.linenumber = linenumber
        self.block = block
        self.block.entries.append(self)

    def get_single_value(self, path=None):
        """ Get a single value from the entry's path. """
        if not path:
            return self.path[0]

        ps = path.split(':')
        for entry in self.path:
            if not ps:
                return entry
            if entry == ps[0]:
                ps = ps[1:]

    def get_path(self, path) -> list:
        """ Get values from the entry matching the specified path. """
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
        return f"<ConfigBlockEntry 'Block: {self.block.name}', File: '{self.filename}', Line: '{self.linenumber}', Path: '{self.path}'>"


class ConfigBlock:
    def __init__(self, filename, linenumber, name, value=None):
        self.path = None
        self.name = name
        self.value = value
        self.filename = filename
        self.linenumber = linenumber
        self.entries = []
        IRCD.configuration.entries.append(self)

    def get_single_value(self, path):
        """ Get a single value from entries matching the path. """
        for item in self.entries:
            ps = path.split(':')
            for entry in item.path:
                if not ps:
                    # Handle escape sequences in strings
                    if isinstance(entry, str):
                        entry = entry.encode().decode("unicode_escape")
                    return entry
                if entry == ps[0]:
                    ps = ps[1:]

    def get_path(self, path):
        """ Get all values from entries matching the path. """
        entries = self.entries.copy()
        blocks = IRCD.configuration.get_blocks(self.name)

        # Collect all entries from blocks with the same name
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
        """ Get a specific item by name. """
        if result := next((i for i in self.entries if i.get_path(itemname)), 0):
            return result
        return 0

    def get_items(self, itemname=''):
        """ Get all items matching a name pattern. """
        if not itemname:
            return [i for i in self.entries]
        return [i for i in self.entries if i.get_path(itemname)]

    def get_all_entries(self):
        """ Get all entries from this block and blocks with the same name. """
        entries = self.entries.copy()
        blocks = IRCD.configuration.get_blocks(self.name)

        for block in blocks:
            for entry in [entry for entry in block.entries if entry not in entries]:
                entries.append(entry)
        return entries

    def get_list_from_path(self, path=''):
        """ Get a list of values from entries matching a path pattern. """
        result = []
        if not path:
            # If no path specified, return all entry values
            for match in self.entries:
                for entry_item in match.path:
                    result.append(entry_item)
            return result

        ps = path.split(':')
        for match in self.get_items(path):
            path_idx = 0
            for entry_item in match.path:
                current_path = ps[path_idx] if path_idx < len(ps) else None
                if entry_item == current_path:
                    path_idx += 1
                    if path_idx == len(ps):
                        result.append(' '.join(match.path[path_idx:]))
                        path_idx = 0
                        continue

        return result

    def __str__(self):
        return f"<ConfigBlock '{self.name}'>"
