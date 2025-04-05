import ipaddress
import os
import re
import socket

from classes.conf_entries import ConnectClass, Allow, Listen, Spamfilter, Operclass, Oper, Link, Alias, Module, Except, Ban, Require, Mask
from handle.functions import valid_expire
from handle.core import IRCD
from handle.logger import logging


class ConfErrors:
    entries = []


class ConfWarnings:
    entries = []


def conf_warning(*args, **kwargs):
    conf_error(*args, **kwargs, warning=1)


def conf_error(message, block=None, item=None, warning=0):
    source = None
    if item:
        source = f"{item.filename}:{item.linenumber}"
    elif block:
        source = f"{block.filename}:{block.linenumber}"

    msg = f"{source + ': ' if source else ' '}{message}"
    if not warning:
        ConfErrors.entries.append(msg)
    else:
        ConfWarnings.entries.append(msg)


def load_module(package):
    package = "modules." + package.replace('/', '.')
    if not IRCD.get_module_by_package(package):
        Module(name=package, module=None)


def check_required_items(block, required, return_missing=False):
    missing = []
    for item in required:
        if not block.get_path(item):
            missing.append(item)
            conf_error(f"Block '{block.name}' is missing item '{item}'", block=block)

    return missing if return_missing else len(missing) == 0


def config_test_me(block):
    if not (server_item := block.get_item("server")):
        conf_error("missing 'server' entry", block)

    if not (name_item := block.get_item("name")):
        conf_error("missing 'name' entry", block)

    if not (sid_item := block.get_item("sid")):
        conf_error("missing 'sid' entry", block)

    if sid_item and (sid_value := block.get_single_value("sid")):
        if not re.match(r"^[0-9][A-Za-z0-9][A-Za-z0-9]$", sid_value):
            conf_error(f"Invalid 'sid' in {block.name} {{ }} block. Must be 3 characters, starting with a number.", block, sid_item)
            return 0

    if server_item and name_item and sid_item:
        IRCD.me.name = block.get_single_value("server")
        if not IRCD.me.name:
            conf_error(f"Missing 'server' value in {block.name} {{ }} block.", block)

        IRCD.me.info = block.get_single_value("name")
        if not IRCD.me.info:
            conf_error(f"Missing 'name' value in {block.name} {{ }} block.", block)

        IRCD.me.id = block.get_single_value("sid").upper()
        if not IRCD.me.id:
            conf_error(f"Missing 'sid' value in {block.name} {{ }} block.", block)


def config_test_admin(block):
    valid_lines = []

    for entry in block.entries:
        if not entry.path:
            continue

        if len(entry.path) > 1:
            conf_error("Another block found in admin { } block. Please only add single lines.", block=block, item=entry)
            continue

        line = entry.path[0]

        if not line.strip():
            conf_error("Empty or invalid line found in admin { } block.", item=entry)
            continue

        if line in valid_lines:
            conf_error("Duplicate line found in admin { } block.", item=entry)
            continue

        valid_lines.append(line)


def config_test_settings(block):
    required = ["throttle", "nickflood", "regtimeout", "cloak-key", "modes-on-connect", "modes-on-join", "resolvehost"]
    check_required_items(block, required)

    def check_with_pattern(check, pattern_func, error_msg):
        if items := block.get_items(check):
            item = items[0]
            value = block.get_single_value(check)
            if not value:
                return conf_error(f"Missing '{check}' value", block, item)

            if not pattern_func(value):
                return conf_error(error_msg.format(check=check, value=value), block, item)

            return value
        return None

    def check_settings_modes_on_join():
        if items := block.get_items("modes-on-join"):
            item, modes = items[0], block.get_single_value("modes-on-join")
            if not modes:
                return

            valid = 1
            for mode in modes.split()[0]:
                if mode in 'vhoaqbeI':
                    conf_error(f"modes-on-join may not contain: {mode}", block, item)
                    valid = 0

            if valid:
                params = []
                paramcount = 0
                if len(modes.split()) > 1:
                    params = modes.split()[1:]
                validmodes, validparams = [], []

                for mode in modes.split()[0]:
                    if not (cmode := IRCD.get_channelmode_by_flag(mode)):
                        continue
                    if mode in IRCD.get_parammodes_str():
                        if len(params) <= paramcount:
                            continue
                        param = params[paramcount]
                        param = cmode.conv_param(param)
                        validparams.append(param)
                    validmodes.append(mode)

                final = f"{''.join(validmodes)}{' ' + ' '.join(validparams) if validparams else ''}"
                IRCD.set_setting("modes-on-join", final)

    def check_settings_modes_on_connect():
        if items := block.get_items("modes-on-connect"):
            item, modes = items[0], block.get_single_value("modes-on-connect")
            if not modes:
                return

            forbid = ''.join(m for m in modes if m in "oqrstzHSW")
            if forbid:
                conf_error(f"forbidden modes in modes-on-connect: {forbid}", block, item)

    def check_settings_resolvehost():
        if items := block.get_items("resolvehost"):
            item, value = items[0], block.get_single_value("resolvehost")
            true_values = ["yes", 'y', '1', "true"]
            false_values = ["no", 'n', '0', "false"]

            if not value:
                return conf_error("missing 'resolvehost' value", block, item)

            if value not in true_values + false_values:
                conf_error(f"invalid 'resolvehost' value: {value}. Must be 'yes' or 'no'.", block, item)
            else:
                IRCD.set_setting("resolvehost", value in true_values)

    def check_settings_format_values():
        # Check throttle and nickflood (same format: num:num)
        for check in ["throttle", "nickflood"]:
            value = check_with_pattern(check, lambda v: ':' in v and all(p.isdigit() for p in v.split(':')),
                                       "Invalid `{check}` value: {value}. Must be <num>:<num> format. Example: 3:30.")
            if value:
                IRCD.set_setting(check, value)

        value = check_with_pattern("regtimeout", lambda v: v.isdigit(), "Invalid `{check}` value: {value}."
                                                                        "Must be a number in seconds.")
        if value:
            value_int = int(value)
            if value_int < 1:
                value = "1"
            elif value_int > 60:
                value = "60"
            IRCD.set_setting("regtimeout", value)

    def check_settings_oper_auto_join():
        if items := block.get_items("oper-auto-join"):
            item, value = items[0], block.get_single_value("oper-auto-join")

            if not value:
                return conf_error("Missing `oper-auto-join` value. Must be a valid channel.", block, item)

            if value[0] not in IRCD.CHANPREFIXES:
                return conf_error(f"Invalid `oper-auto-join` value: {value}."
                                  f"Must be a valid channel type. Types are: {IRCD.CHANPREFIXES}", block, item)

            if not IRCD.is_valid_channelname(value):
                return conf_error(f"Invalid `oper-auto-join` value: {value}. Invalid channel name.", block, item)

            if "," in value:
                return conf_error(f"Invalid `oper-auto-join` value: {value}. Please only provide one channel.", block, item)

            IRCD.set_setting("oper-auto-join", value)

    def check_settings_optional_values():
        for check in ["static-part", "cloak-prefix"]:
            if items := block.get_items(check):
                value = block.get_single_value(check)
                if value and value.strip():
                    IRCD.set_setting(check, value)

    def check_settings_cloak_key():
        if items := block.get_items("cloak-key"):
            item, value = items[0], block.get_single_value("cloak-key")

            if not value:
                return conf_error("Missing 'cloak-key' value", block, item)

            value = value.strip()
            error_msg = "Cloak-key must be at least 64 characters long, and contain at least 1 lowercase, 1 uppercase, and 1 number"

            if not value:
                return conf_error(f"Missing `cloak-key` value. {error_msg}.", block, item)

            if len(value) < 64:
                return conf_error(f"Invalid `cloak-key` value. {error_msg}: cloak-key too short", block, item)

            if not re.search(r'[a-z]', value):
                return conf_error(f"Invalid `cloak-key` value. {error_msg}: missing lowercase characters", block, item)

            if not re.search(r'[A-Z]', value):
                return conf_error(f"Invalid `cloak-key` value. {error_msg}: missing uppercase characters", block, item)

            if not re.search(r'[0-9]', value):
                return conf_error(f"Invalid `cloak-key` value. {error_msg}: missing numbers", block, item)

            if not bool(re.match(r'^[a-zA-Z0-9]+$', value)):
                return conf_error(f"Invalid `cloak-key` value. {error_msg}: special characters are not allowed", block, item)

            IRCD.set_setting("cloak-key", value)

    check_settings_modes_on_join()
    check_settings_modes_on_connect()
    check_settings_resolvehost()
    check_settings_format_values()
    check_settings_oper_auto_join()
    check_settings_optional_values()
    check_settings_cloak_key()

    for entry in block.get_all_entries():
        if not entry.path or len(entry.path) != 2:
            continue
        name, value = entry.path
        if IRCD.configuration.setting_empty(name):
            IRCD.set_setting(name, value)


def config_test_class(block):
    if not (class_name := block.value):
        conf_error("class is missing a name", block)
        return

    sendq, recvq, maxc = block.get_single_value("sendq"), block.get_single_value("recvq"), block.get_single_value("max")

    missing = []
    if not sendq:
        missing.append("sendq")
        conf_error(f"'sendq' is missing from class '{class_name}'", block)
    if not recvq:
        missing.append("recvq")
        conf_error(f"'recvq' is missing from class '{class_name}'", block)
    if not maxc:
        missing.append("max")
        conf_error(f"'max' is missing from class '{class_name}'", block)

    if missing:
        return

    for name, value in [("sendq", sendq), ("recvq", recvq), ("max", maxc)]:
        if not value.isdigit():
            item = block.get_item(name)
            conf_error(f"Invalid '{name}': must be a number", block, item)
            return

    ConnectClass(class_name, sendq, recvq, maxc)


def config_test_allow(block):
    required = ["mask", "class", "maxperip"]
    if not check_required_items(block, required):
        return

    mask = Mask(block)
    connectclass_name, maxperip = block.get_single_value("class"), block.get_single_value("maxperip")

    if mask and connectclass_name and maxperip:
        allow = Allow(mask=mask, connectclass_name=connectclass_name, maxperip=maxperip)

        if password := block.get_single_value("password"):
            allow.password = password

        if options := block.get_items("options"):
            for option in options:
                opt = option.get_single_value("options")
                allow.options.append(opt)


def config_test_listen(block):
    def is_port_in_use(host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                location = (host, port)
                s.bind(location)
                s.close()
                return 0, 0
            except OSError as ex:
                s.close()
                if ex.errno in [13, 10013]:
                    return 1, f"Could not bind to port '{port}': Permission denied."
                if ex.errno in [98, 48, 10048]:
                    return 1, f"Port '{port}' is already in use on this machine"
                return 1, 0
            except Exception as ex:
                logging.exception(ex)
                s.close()
                return 1, 0

    if not (ip_item := block.get_item("ip")):
        conf_error("'ip' is missing from listen block", block)
        return

    if not (port_item := block.get_item("port")):
        conf_error("'port' is missing from listen block", block)
        return

    ip, port = block.get_single_value("ip"), block.get_single_value("port")

    if ip != '*':
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return conf_error(f"Invalid IP address: {ip}", block=block, item=ip_item)

    if IRCD.configuration.get_listen_by_port(port):
        return conf_error(f"Port '{port}' is already defined before.", block=block, item=port_item)

    if not port.isdigit():
        return conf_error(f"Port '{port}' is invalid. Must be a number in range 1024-65535.", block=block, item=port_item)

    if not 1024 <= int(port) <= 65535:
        return conf_error(f"Port '{port}' is invalid. Must be in range 1024-65535.", block=block, item=port_item)

    # Check if port is in use.
    check_ip = "127.0.0.1" if ip == '*' else ip
    port_error, errmsg = is_port_in_use(check_ip, int(port))

    if port_error == 1 and int(port) not in IRCD.configuration.our_ports:
        return conf_error(errmsg or f"Unable to bind to port '{port}'", block=block, item=port_item)

    # Don't re-bind already listening sockets.
    if IRCD.configuration.get_listen_by_port(port):
        return

    listen = Listen(ip=ip, port=port)

    for check, attr in [("tls-options:certificate-file", "cert"), ("tls-options:key-file", "key")]:
        if file_item := block.get_item(check):
            file_path = block.get_single_value(check)
            if not os.path.isfile(file_path):
                default_file = "tls/server.cert.pem" if attr == "cert" else "tls/server.key.pem"
                if IRCD.rehashing or file_path != default_file:
                    conf_error(f"Cannot find {attr} file `{file_path}`", item=file_item)
            else:
                setattr(listen, attr, file_path)

    if options := block.get_items("options"):
        for option in options:
            opt = option.get_single_value('options')
            listen.verify_option(opt)


def config_test_spamfilter(block):
    required = ["match-type", "match", "target", "reason"]
    if not check_required_items(block, required):
        return

    spamfilter_reason = block.get_single_value("reason")
    spamfilter_match = block.get_single_value("match")
    spamfilter_match_type = block.get_single_value("match-type")
    match_type_item = block.get_item("match-type")

    # Validate match type
    valid_types = ["simple", "regex"]
    if spamfilter_match_type not in valid_types:
        conf_error(f"Invalid match-type in '{block.name}': {spamfilter_match_type}."
                   f"Must be one of the following: {', '.join(valid_types)}", block, match_type_item)
        spamfilter_match_type = None

    # Check targets
    valid_targets = {
        "channel": 'c', "private": 'p', "private-notice": 'n',
        "channel-notice": 'N', "part": 'P', "quit": 'Q',
        "topic": 't', "away": 'a'
    }

    spamfilter_targets = []
    for target_item in block.get_items("target"):
        target = target_item.path[1]
        if target not in valid_targets:
            conf_error(f"Invalid target in '{block.name}': {target}."
                       f"Must be one of the following: {', '.join(valid_targets.keys())}", block=block, item=target_item)
            continue
        spamfilter_targets.append(valid_targets[target])
    spamfilter_targets = ''.join(spamfilter_targets)

    valid_actions = ["warn", "block", "kill", "gzline"]
    spamfilter_action = block.get_single_value("action")
    if spamfilter_action not in valid_actions:
        conf_error(f"Invalid action: {spamfilter_action}", block)
        spamfilter_action = None

    spamfilter_duration = 0
    if spamfilter_action == "gzline":
        spamfilter_duration = block.get_single_value("duration") or "1d"
        spamfilter_duration = valid_expire(spamfilter_duration) or valid_expire("1d")

    # Check for duplicates
    for sf in IRCD.configuration.spamfilters:
        if sf.match.lower() == spamfilter_match.lower() and sf.match_type.lower() == spamfilter_match_type.lower():
            conf_error(f"Duplicate spamfilter entry found in {sf.conf_file}: {spamfilter_match} ({spamfilter_match_type})", block=block)

    # Create spamfilter if everything is valid
    requirements = [spamfilter_match_type, spamfilter_match, spamfilter_targets, spamfilter_action, spamfilter_reason]
    if all(requirements):
        Spamfilter(
            match_type=spamfilter_match_type,
            match=spamfilter_match,
            target=spamfilter_targets,
            action=spamfilter_action,
            duration=spamfilter_duration,
            reason=spamfilter_reason,
            conf_file=block.filename
        )


def config_test_operclass(block):
    if not block.value:
        conf_error("operclass is missing a name", block)
        return

    if not check_required_items(block, ["permissions"]):
        return

    operclass_permissions = []
    for perm in block.get_items("permissions"):
        p = perm.path[2:]
        operclass_permissions.append(p)

    operclass = Operclass(block.value, permissions=operclass_permissions)
    if parent := block.get_single_value("parent"):
        operclass.parent = parent


def config_test_oper(block):
    if not (oper_name := block.value):
        return conf_error("Oper block is missing a name", block=block)

    if next((o for o in IRCD.configuration.opers if o.name == oper_name), 0):
        return conf_error(f"Duplicate oper name found: {oper_name}", block=block)

    required = ["class", "operclass", "mask"]
    missing_items = []
    for item in required:
        if not block.get_item(item):
            missing_items.append(item)

    if missing_items:
        return conf_error(f"Block '{block.name} {block.value}' is missing item: {', '.join(missing_items)}", block)

    connectclass = block.get_single_value("class")
    operclass = block.get_single_value("operclass")
    password = block.get_single_value("password")
    oper_mask = Mask(block)

    for oper_mask_item in block.get_items("mask"):
        path = oper_mask_item.path
        mask_what = path[2] if len(path) > 2 else None
        mask_value = path[3] if len(path) > 3 else None

        if not mask_what:
            continue

        if mask_value and mask_what not in oper_mask.types:
            errmsg = f"Unrecognized mask type in {block.name} {{ }} mask:{mask_what}. Valid: {', '.join(oper_mask.types)}"
            conf_error(errmsg, item=oper_mask_item)
            continue

        if mask_what in oper_mask.types and not mask_value:
            errmsg = f"Missing value for oper {{ {oper_name} }} mask:{mask_what}"
            conf_error(errmsg, item=oper_mask_item)
            continue

        # Check for duplicate certfp/account
        if mask_what == "certfp":
            for conf_oper in IRCD.configuration.opers:
                if mask_value in conf_oper.certfp:
                    conf_error(f"The cert fingerprint you provided for oper block '{oper_name}'"
                               f"is already in use by oper block '{conf_oper.name}'", item=oper_mask_item)

        if mask_what == "account":
            for conf_oper in IRCD.configuration.opers:
                if mask_value in conf_oper.account_mask:
                    conf_error(f"The account mask you provided for oper block '{oper_name}'"
                               f"is already in use by oper block '{conf_oper.name}'", item=oper_mask_item)

    oper = Oper(oper_name, connectclass, operclass, password, oper_mask)

    for attr in ["modes", "snomasks", "operhost", "swhois"]:
        if value := block.get_single_value(attr):
            setattr(oper, attr, value)


def config_test_link(block):
    if not (link_name := block.value):
        return conf_error("Link block is missing a name", block)

    if IRCD.get_link(link_name):
        return conf_error(f"Link block '{block.value}' already exists.")

    required = ["class"]
    if missing := [item for item in required if not block.get_item(item)]:
        conf_error(f"Block '{block.name} {block.value}' is missing item: {', '.join(missing)}", block)
        return

    if not block.get_items("outgoing") and not block.get_items("incoming"):
        conf_error(f"Link block '{block.value}' is missing required 'outgoing' or 'incoming' settings", block)
        return

    mask = Mask(block)
    link = Link(
        name=link_name,
        password=None,
        connectclass=block.get_single_value("class"),
        incoming_mask=mask
    )

    if password := block.get_single_value("password"):
        link.password = password

    for item in block.get_items("outgoing"):
        outgoing_item = item.get_single_value("outgoing")
        if outgoing_item == "host":
            check_host = item.get_single_value("host")
            try:
                ipaddress.ip_network(check_host)
            except ValueError:
                conf_error(f"Invalid outgoing IP for link {link_name}: {check_host}", block=block)
            link.outgoing["host"] = check_host

        elif outgoing_item == "port":
            link.outgoing["port"] = item.get_single_value("port")

        for option in item.get_path("options"):
            link.outgoing_options.append(option)

    for entry in block.get_items():
        if entry.path[1] == "options" and len(entry.path) > 2:
            link.options.append(':'.join(entry.path[2:]))

    if fingerprint := block.get_single_value("fingerprint"):
        link.fingerprint = fingerprint

    auth = {"password": None, "fingerprint": None, "common-name": None}

    if auth_items := block.get_items("auth"):
        for item in auth_items:
            auth_item = item.get_single_value("auth")

            if auth_item == "password":
                auth["password"] = item.get_single_value("password")

            elif auth_item == "fingerprint":
                fingerprint = item.get_single_value("fingerprint")
                if not re.match(r"[A-Fa-f0-9]{64}$", fingerprint):
                    conf_error(f"Invalid certificate fingerprint: {fingerprint}. Must match: [A-Fa-f0-9]{64}", item=item)
                    continue
                auth["fingerprint"] = fingerprint

            elif auth_item == "common-name":
                cn = item.get_single_value("common-name")
                auth["common-name"] = cn.replace(' ', '_')
    else:
        if not password:
            conf_error(f"Missing auth block in link '{block.value}'")
        else:
            conf_warning(
                f"Link block '{block.value}' uses the deprecated 'password' option. "
                f"Use the 'auth' sub-block instead. Check conf/examples/links.example.conf for details.")

    link.auth = auth


def config_test_require(block):
    if not (require_what := block.value):
        return conf_error("require is missing a type", block)

    if require_what not in ["authentication"]:
        return conf_error(f"Unknown require type: {require_what}", block)

    required = ["mask", "reason"]
    if not all(block.get_path(require_what + ':' + item) for item in required):
        for item in required:
            if not block.get_path(require_what + ':' + item):
                conf_error(f"Block '{block.name} {block.value}' is missing item '{item}'", block=block)
        return

    require_mask = Mask(block)
    Require(require_what, mask=require_mask, reason=block.get_single_value("reason"))


def config_test_alias(block):
    if not (alias_name := block.value):
        conf_error("alias is missing a name", block)
        return

    if not check_required_items(block, ["type"]):
        return

    # Create alias
    alias = Alias(alias_name, block.get_single_value("type"))

    # Set target (defaults to alias name)
    alias.target = block.get_single_value("target") or alias.name

    # Add options
    if options := block.get_items("options"):
        for option in options:
            opt = option.get_single_value('options')
            alias.options.append(opt)


def config_test_except(block):
    if not (except_name := block.value):
        return conf_error("Except block is missing a name. Example: except tkl { ... }", block)

    # Check required fields
    if not block.get_item("mask"):
        conf_error(f"Block '{block.name} {block.value}' is missing item: mask", block)
        return

    # Create except
    except_mask = Mask(block)
    types = []

    # Process types
    valid_types = ["kline", "gline", "zline", "gzline", "shun", "spamfilter",
                   "dnsbl", "throttle", "require", "kill"]

    for type_item in block.get_items("type"):
        path = type_item.path
        type_what = path[2] if len(path) > 2 else None

        if not type_what or type_what not in valid_types:
            conf_error(f"Invalid except:type: {type_what}", item=type_item)
            continue

        types.append(type_what)

    # Validate masks
    for mask_item in block.get_items("mask"):
        path = mask_item.path
        if len(path) <= 2:
            continue

        mask_what = path[2].removeprefix('.').removesuffix('.')
        mask_value = path[3] if len(path) > 3 else None

        if not mask_what:
            continue

        if mask_value and mask_what not in except_mask.types:
            errmsg = f"Unrecognized mask type in except {block.name} {{ }} mask:{mask_what}. Valid: {', '.join(except_mask.types)}"
            conf_error(errmsg, item=mask_item)
            continue

        if mask_what in except_mask.types and not mask_value:
            errmsg = f"Missing value for except {block.name} {{ }} mask:{mask_what}"
            conf_error(errmsg, item=mask_item)
            continue

    # Create except
    e = Except(name=except_name, mask=except_mask, types=types)

    # Add comment if specified
    if comment := block.get_single_value("comment"):
        e.comment = comment


def config_test_ulines(block):
    if not hasattr(IRCD.me, "name"):
        return

    ulines = []
    for entry in block.entries:
        server = entry.get_single_value().lower()

        # Skip duplicates
        if server in ulines:
            continue

        if server == IRCD.me.name.lower():
            conf_error(f"Invalid uline server: {server}. Cannot be this server!", block=block, item=entry)
            continue

        ulines.append(server)

    IRCD.set_setting("ulines", ulines)


def config_test_bans(block):
    if not (ban_type := block.value):
        conf_error("Ban block is missing a name. Example: ban nick { ... }", block)
        return

    required = ["mask", "reason"]
    if missing := [item for item in required if not block.get_item(item)]:
        return conf_error(f"Block '{block.name} {block.value}' is missing item: {', '.join(missing)}", block)

    bans_mask = Mask(block)
    reason = block.get_single_value("reason")

    if not reason.strip():
        return conf_error(f"Block '{block.name} {block.value}' has an empty reason", block)

    Ban(ban_type=ban_type, mask=bans_mask, reason=reason)
