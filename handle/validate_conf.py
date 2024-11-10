import ipaddress
import os
import re
import socket

from classes.conf_entries import ConnectClass, Allow, Listen, Spamfilter, Operclass, Oper, Link, Alias, Module, Except, Ban, Require, Mask
from handle.functions import logging, valid_expire
from handle.core import IRCD


class ConfErrors:
    entries = []
    paths = []


class ConfWarnings:
    entries = []
    paths = []


def conf_warning(*args, **kwargs):
    conf_error(*args, **kwargs, warning=1)


def conf_error(errmsg, block=None, item=None, filename=None, linenumber=0, warning=0):
    if item:
        block = item.block
        if not linenumber:
            linenumber = str(item.linenumber)
    elif block:
        if not linenumber:
            linenumber = str(block.linenumber)
    if not filename and block:
        filename = block.filename
    if linenumber:
        linenumber = str(linenumber)
    path = f"{filename + ':' if filename else ''}{' ' if not block else ''}{linenumber + ': ' if linenumber else ''}"
    errstr = path.strip() + f"{errmsg}".strip()
    if not warning:
        if errstr not in ConfErrors.entries and path not in ConfErrors.paths:
            ConfErrors.entries.append(errstr)
    else:
        if errstr not in ConfWarnings.entries and path not in ConfWarnings.paths:
            ConfWarnings.entries.append(errstr)


def load_module(package):
    package = "modules." + package.replace('/', '.')
    if not IRCD.configuration.get_module_by_package(package):
        Module(name=package, module=None)


def config_test_me(block):
    valid_items = ["server", "name", "sid"]
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
            conf_error(f"Missing 'server' value in {block.name} {{ }} block.")
        IRCD.me.info = block.get_single_value("name")
        if not IRCD.me.info:
            conf_error(f"Missing 'name' value in {block.name} {{ }} block.")
        IRCD.me.id = block.get_single_value("sid").upper()
        if not IRCD.me.id:
            conf_error(f"Missing 'sid' value in {block.name} {{ }} block.")

    for entry in block.entries:
        item = entry.path[0]
        if item not in valid_items:
            conf_error(f"Invalid item in {block.name} {{ }} block: '{item}'", block)


def config_test_admin(block):
    valid = []
    for entry in block.entries:
        if len(entry.path) > 1:
            conf_error(f"Another block found in admin {{ }} block. Please only add single lines.", block=block)
            logging.debug(entry.path)
            break
        line = entry.path[0]
        if not line.strip():
            conf_error(f"Empty or invalid line found in admin {{ }} block.", item=entry)
            break
        if line in valid:
            conf_error(f"Duplicate line found in admin {{ }} block.", item=entry)
            break
        valid.append(line)


def config_test_settings(block):
    required = ["throttle", "nickflood", "regtimeout", "cloak-key", "modes-on-connect", "modes-on-join", "resolvehost"]
    for item in required:
        if not block.get_path(item):
            conf_error(f"Block '{block.name}' is missing item '{item}'", filename=block.filename)

    def check_settings_modes_on_join():
        check = "modes-on-join"
        if item := block.get_item(check):
            modes = block.get_single_value(check)

            # Check valid modes in Configuration.post_process()
            valid = 1
            for mode in modes.split()[0]:
                match mode:
                    case 'v' | 'h' | 'o' | 'a' | 'q' | 'b' | 'e' | 'I':
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
                IRCD.set_setting(check, final)

    def check_settings_modes_on_connect():
        check = "modes-on-connect"
        if item := block.get_item(check):
            modes = block.get_single_value(check)
            forbid = ''
            for mode in modes:
                if mode in "oqrstzHSW" and mode not in forbid:
                    forbid += mode
            if forbid:
                conf_error(f"forbidden modes in modes-on-connect: {forbid}", block, item)

    def check_settings_resolvehost():
        check = "resolvehost"
        if item := block.get_item(check):
            value = block.get_single_value(check)
            true_values = ["yes", 'y', '1', "true"]
            false_values = ["no", 'n', '0', "false"]
            if not value:
                return conf_error(f"missing '{check}' value", block, item)
            if value not in true_values + false_values:
                conf_error(f"invalid '{check}' value: {value}. Must be 'yes' or 'no'", block, item)
            else:
                IRCD.set_setting(check, value in true_values)

    def check_settings_throttle():
        check = "throttle"
        if item := block.get_item(check):
            value = block.get_single_value(check)
            if ':' not in value:
                return conf_error(f"Invalid `{check}` value: {value}. Must be <num>:<num> format. Example: 3:30.", block, item)
            conns, seconds = value.split(':')
            if not conns.isdigit() or not seconds.isdigit():
                return conf_error(f"Invalid `{check}` value: {value}. Must be <num>:<num> format. Example: 3:30.", block, item)

            IRCD.set_setting(check, value)

    def check_settings_nickflood():
        check = "nickflood"
        if item := block.get_item(check):
            value = block.get_single_value(check)
            if ':' not in value:
                return conf_error(f"Invalid `{check}` value: {value}. Must be <num>:<num> format. Example: 3:30.", block, item)
            conns, seconds = value.split(':')
            if not conns.isdigit() or not seconds.isdigit():
                return conf_error(f"Invalid `{check}` value: {value}. Must be <num>:<num> format. Example: 3:30.", block, item)

            IRCD.set_setting(check, value)

    def check_settings_regtimeout():
        check = "regtimeout"
        if item := block.get_item(check):
            value = block.get_single_value(check)
            if not value.isdigit():
                return conf_error(f"Invalid `{check}` value: {value}. Must be a number in seconds.", block, item)
            if int(value) < 1:
                value = 1
            elif int(value) > 60:
                value = 60
            IRCD.set_setting(check, value)

    def check_settings_oper_auto_join():
        check = "oper-auto-join"
        if item := block.get_item(check):
            value = block.get_single_value(check)
            if not value:
                return conf_error(f"Missing `{check}` value. Must be a valid channel.", block, item)
            if value[0] not in IRCD.CHANPREFIXES:
                return conf_error(f"Invalid `{check}` value: {value}. Must be a valid channel type. Types are: {IRCD.CHANPREFIXES}", block, item)
            if not IRCD.is_valid_channelname(value):
                return conf_error(f"Invalid `{check}` value: {value}. Invalid channel name.", block, item)
            if "," in value:
                return conf_error(f"Invalid `{check}` value: {value}. Please only provide one channel.", block, item)

            IRCD.set_setting(check, value)

    def check_settings_static_part():
        check = "static-part"
        if item := block.get_item(check):
            value = block.get_single_value(check)
            if not value.strip():
                # Why throw error on empty value? Just leave it empty.
                return  # conf_error(f"Missing `{check}` value.", block, item)

            IRCD.set_setting(check, value)

    def check_settings_cloak_prefix():
        check = "cloak-prefix"
        if item := block.get_item(check):
            value = block.get_single_value(check)
            if not value.strip():
                # Why throw error on empty value? Just leave it empty.
                return  # conf_error(f"Missing `{check}` value.", block, item)

            IRCD.set_setting(check, value)

    def check_settings_cloak_key():
        check = "cloak-key"
        if item := block.get_item(check):
            value = block.get_single_value(check).strip()
            error_msg = f"Cloak-key must be at least 64 characters long, and contain at least 1 lowercase, 1 uppercase, and 1 number"
            if not value:
                return conf_error(f"Missing `{check}` value. {error_msg}.", block, item)
            if len(value) < 64:
                return conf_error(f"Invalid `{check}` value. {error_msg}: cloak-key too short", block, item)
            if not re.search(r'[a-z]', value):
                return conf_error(f"Invalid `{check}` value. {error_msg}: missing lowercase characters", block, item)
            if not re.search(r'[A-Z]', value):
                return conf_error(f"Invalid `{check}` value. {error_msg}: missing uppercase characters", block, item)
            if not re.search(r'[0-9]', value):
                return conf_error(f"Invalid `{check}` value. {error_msg}: missing numbers", block, item)
            if not bool(re.match(r'^[a-zA-Z0-9]+$', value)):
                return conf_error(f"Invalid `{check}` value. {error_msg}: special characters are not allowed", block, item)

            IRCD.set_setting(check, value)

    check_settings_modes_on_join()
    check_settings_modes_on_connect()
    check_settings_resolvehost()
    check_settings_throttle()
    check_settings_nickflood()
    check_settings_regtimeout()
    check_settings_oper_auto_join()
    check_settings_static_part()
    check_settings_cloak_prefix()
    check_settings_cloak_key()

    for entry in block.get_all_entries():
        if len(entry.path) != 2:
            # conf_error(f"Invalid conf entry: '{entry.path[0]}'", entry.block, entry)
            continue
        name, value = entry.path
        if IRCD.configuration.setting_empty(name):
            IRCD.set_setting(name, value)


def config_test_class(block):
    if not block.value:
        conf_error(f"class is missing a name", block)
        return

    class_name = block.value
    sendq, recvq, maxc = block.get_single_value("sendq"), block.get_single_value("recvq"), block.get_single_value("max")
    if not sendq:
        conf_error(f"'sendq' is missing from class '{class_name}'", block)
    if not recvq:
        conf_error(f"'recvq' is missing from class '{class_name}'", block)
    if not maxc:
        conf_error(f"'max' is missing from class '{class_name}'", block)

    sendq_item = block.get_item("sendq")
    recvq_item = block.get_item("recvq")
    maxc_item = block.get_item("max")

    if sendq and not sendq.isdigit():
        conf_error(f"Invalid 'sendq': must a be number", block, sendq_item)

    if recvq and not recvq.isdigit():
        conf_error(f"Invalid 'recvq': must a be number", block, recvq_item)

    if maxc and not maxc.isdigit():
        conf_error(f"Invalid 'max': must a be number", block, maxc_item)

    if sendq and recvq and maxc:
        ConnectClass(class_name, sendq, recvq, maxc)


def config_test_allow(block):
    required = ["mask", "class", "maxperip"]
    for item in required:
        if not block.get_path(item):
            conf_error(f"Block '{block.name}' is missing item '{item}'", block)

    mask = Mask(block)

    _class, maxperip = block.get_single_value("class"), block.get_single_value("maxperip")
    if mask and _class and maxperip:
        allow = Allow(mask=mask, class_obj=_class, maxperip=maxperip)
        if password := block.get_single_value("password"):
            allow.password = password
        if options := block.get_items("options"):
            for option in options:
                opt = option.get_single_value("options")
                allow.options.append(opt)


def config_test_listen(block):
    def is_port_in_use(host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                location = (host, port)
                s.bind(location)  # Try to bind to the port.
                close_port_check(s)
                return 0, 0  # If the bind succeeds, the port is not in use.
            except OSError as ex:
                close_port_check(s)
                if ex.errno in [13, 10013]:
                    # Permission denied.
                    return 1, f"Could not bind to port '{port}': Permission denied."
                if ex.errno in [98, 48, 10048]:
                    # Already in use.
                    return 1, f"Port '{port}' is already in use on this machine"
                return 1, 0
            except Exception as ex:
                close_port_check(s)
                return 1, 0

    def close_port_check(s):
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.shutdown(socket.SHUT_WR)
        except:
            s.close()
        s.close()

    if not (ip_item := block.get_item("ip")):
        conf_error(f"'ip' is missing from listen block", block)

    if not (port_item := block.get_item("port")):
        conf_error(f"'port' is missing from listen block", block)

    if ip_item and port_item:
        ip, port = block.get_single_value("ip"), block.get_single_value("port")
        if IRCD.configuration.get_listen_by_port(port):
            return conf_error(f"Port '{port}' is already defined before.", block=block, item=port_item)

        if not port.isdigit():
            return conf_error(f"Port '{port}' is invalid. Must be a number in range 1024-65535.", block=block, item=port_item)

        if not 1024 <= int(port) <= 65535:
            return conf_error(f"Port '{port}' is invalid. Must be in range 1024-65535.", block=block, item=port_item)

        check_ip = "127.0.0.1" if ip == '*' else ip
        port_error, errmsg = is_port_in_use(check_ip, int(port))
        if port_error == 1 and int(port) not in IRCD.configuration.our_ports:
            return conf_error(errmsg or f"Unable to bind to port '{port}'", block=block, item=port_item)

        # Don't re-bind already listening sockets.
        if IRCD.configuration.get_listen_by_port(port):
            return

        listen = Listen(ip=ip, port=port)

        check = "tls-options:certificate-file"
        if cert_item := block.get_item(check):
            cert = block.get_single_value(check)
            if not os.path.isfile(cert):
                if IRCD.rehashing or cert != "tls/server.cert.pem":
                    conf_error(f"Cannot find certificate file `{cert}`", item=cert_item)
            else:
                listen.cert = cert

        check = "tls-options:key-file"
        if key_item := block.get_item(check):
            key = block.get_single_value(check)
            if not os.path.isfile(key):
                if IRCD.rehashing or key != "tls/server.key.pem":
                    conf_error(f"Cannot find key file `{key}`", item=key_item)
            else:
                listen.key = key

        if options := block.get_items("options"):
            for option in options:
                opt = option.get_single_value('options')
                listen.verify_option(opt)


def config_test_spamfilter(block):
    spamfilter_targets = []
    spamfilter_duration = None

    required = ["match-type", "match", "target", "reason"]
    for item in required:
        if not block.get_path(item):
            conf_error(f"Block '{block.name}' is missing item '{item}'", block)

    spamfilter_reason = block.get_single_value("reason")
    spamfilter_match = block.get_single_value("match")
    spamfilter_match_type, item = block.get_single_value("match-type"), block.get_item("match-type")

    valid_types = ["simple", "regex"]
    if spamfilter_match_type not in valid_types:
        conf_error(f"Invalid match-type in '{block.name}': {spamfilter_match_type}. Must be one of the following: {', '.join(valid_types)}", block, item)
        spamfilter_match_type = None

    # Checking targets
    valid_targets = ["channel", "private", "private-notice", "channel-notice", "part", "topic", "away"]
    valid_targets_shortened = {
        "channel": 'c',
        "private": 'p',
        "private-notice": 'n',
        "channel-notice": 'N',
        "part": 'P',
        "topic": 't',
        "away": 'a'
    }

    # Spamfilter can have multiple targets.
    target_items = block.get_items("target")
    for target_item in target_items:
        target = target_item.get_single_value("target")
        if target not in valid_targets:
            conf_error(f"Invalid target in '{block.name}': {target}. Must be one of the following: {', '.join(valid_targets)}", block, target_item)
            continue
        spamfilter_targets.append(valid_targets_shortened[target])
    spamfilter_targets = ''.join(spamfilter_targets)

    valid_actions = ["warn", "block", "kill", "gzline"]
    spamfilter_action = block.get_single_value("action")
    if spamfilter_action not in valid_actions:
        conf_error(f"Invalid action: {spamfilter_action}", block)
        spamfilter_action = None

    # If the action is 'gzline', also check for required duration.
    if spamfilter_action == "gzline":
        if not (spamfilter_duration := block.get_single_value("duration")):
            # conf_error(f"Spamfilter entry has 'gzline' action but no duration. Using default of 1d.", block)
            spamfilter_duration = "1d"
        if not (spamfilter_duration := valid_expire(spamfilter_duration)):
            spamfilter_duration = valid_expire("1d")
    if not spamfilter_duration:
        spamfilter_duration = 0

    for sf in IRCD.configuration.spamfilters:
        if sf.match.lower() == spamfilter_match.lower() and sf.match_type.lower() == spamfilter_match_type.lower():
            conf_error(f"Duplicate spamfilter entry found in {sf.conf_file}: {spamfilter_match} ({spamfilter_match_type})", block=block)

    if spamfilter_match_type \
            and spamfilter_match \
            and spamfilter_targets \
            and spamfilter_action \
            and spamfilter_reason:
        Spamfilter(match_type=spamfilter_match_type,
                   match=spamfilter_match,
                   target=spamfilter_targets,
                   action=spamfilter_action,
                   duration=spamfilter_duration,
                   reason=spamfilter_reason,
                   conf_file=block.filename)


def config_test_operclass(block):
    if not block.value:
        conf_error(f"operclass is missing a name", block)
        return
    required = ["permissions"]
    for item in required:
        if not block.get_path(item):
            conf_error(f"Block '{block.name}' is missing item '{item}'", block)

    operclass_permissions = []
    permissions = block.get_items("permissions")
    for perm in permissions:
        p = perm.path[2:]
        operclass_permissions.append(p)

    operclass = Operclass(block.value, permissions=operclass_permissions)
    if parent := block.get_single_value("parent"):
        operclass.parent = parent


def config_test_oper(block):
    if not (oper_name := block.value):
        return conf_error(f"Oper block is missing a name", block=block)
    if next((o for o in IRCD.configuration.opers if o.name == oper_name), 0):
        return conf_error(f"Duplicate oper name found: {oper_name}", block=block)

    required = ["class", "operclass", "mask"]
    missing_items = [item for item in required if not block.get_item(item)]
    if missing_items:
        return conf_error(f"Block '{block.name} {block.value}' is missing item: {', '.join(missing_items)}", block)

    connectclass = block.get_single_value("class")
    operclass = block.get_single_value("operclass")
    password = block.get_single_value("password")
    oper_mask = Mask(block)

    for oper_mask_item in block.get_items("mask"):
        path = oper_mask_item.path
        mask_what = path[2]
        mask_value = None
        if len(path[2:]) > 1:
            mask_value = path[3]
        full_mask = oper_mask_item.path[2:]
        if mask_value and mask_what not in oper_mask.types:
            errmsg = f"Unrecognized mask type in except {block.name} {{ }} mask:{mask_what}. Valid: {', '.join(oper_mask.types)}"
            conf_error(errmsg, item=oper_mask_item)
            continue

        if mask_what in oper_mask.types and not mask_value:
            errmsg = f"Missing value for oper {{ {oper_name} }} mask:{mask_what}"
            conf_error(errmsg, item=oper_mask_item)
            continue

        if mask_what == "certfp":
            for conf_oper in IRCD.configuration.opers:
                if mask_value in conf_oper.certfp:
                    conf_error(f"The cert fingerprint you provided for oper block '{oper_name}' is already in use by oper block '{conf_oper.name}'", item=oper_mask_item)
                    continue

            for conf_oper in IRCD.configuration.opers:
                if mask_value in conf_oper.account_mask:
                    conf_error(f"The account mask you provided for oper block '{oper_name}' is already in use by oper block '{conf_oper.name}'", item=oper_mask_item)
                    continue

    oper = Oper(oper_name, connectclass, operclass, password, oper_mask)
    oper.modes = block.get_single_value("modes")
    oper.snomasks = block.get_single_value("snomasks")
    oper.operhost = block.get_single_value("operhost")
    oper.swhois = block.get_single_value("swhois")


def config_test_link(block):
    if not (link_name := block.value):
        return conf_error(f"Link block is missing a name", block)

    """ Check duplicate link names """
    for link in IRCD.configuration.links:
        if link.name.lower() == link_name.lower():
            return conf_error(f"Link block '{block.value}' already exists.")

    ok = 1

    required = ["class"]
    missing_items = [item for item in required if not block.get_item(item)]
    if missing_items:
        conf_error(f"Block '{block.name} {block.value}' is missing item: {', '.join(missing_items)}", block)
        ok = 0

    if not (outgoing_items := block.get_items("outgoing")) and not (block.get_items("incoming")):
        conf_error(f"Link block '{block.value}' is missing missing required 'outgoing' or 'incoming' settings", block)
        ok = 0

    if ok:
        link = Link(link_name, password=None, connectclass=block.get_single_value("class"))
        if password := block.get_single_value("password"):
            link.password = password
            for item in outgoing_items:
                outgoing_item = item.get_single_value("outgoing")
                if outgoing_item == "host":
                    link.outgoing["host"] = item.get_single_value("host")
                elif outgoing_item == "port":
                    link.outgoing["port"] = item.get_single_value("port")
                for option in item.get_path("options"):
                    link.outgoing_options.append(option)

        for mask_item in block.get_items("incoming:mask"):
            ip = mask_item.path[3]
            if not ip == '*':
                valid_check = ip.replace('*', '0')
                try:
                    ipaddress.ip_address(valid_check)
                except ValueError:
                    conf_error(f"Invalid IP address '{ip}' in incoming:mask", item=mask_item)
                    continue
            if ip in link.incoming_mask:
                continue
            link.incoming_mask.append(ip)

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
                if auth_item == "fingerprint":
                    fingerprint = item.get_single_value("fingerprint")
                    if not re.match(r"[A-Fa-f0-9]{64}$", fingerprint):
                        conf_error(f"Invalid certificate fingerprint: {fingerprint}. Must match: [A-Fa-f0-9]{64}")
                        continue
                    auth["fingerprint"] = fingerprint
                if auth_item == "common-name":
                    cn = item.get_single_value("common-name")
                    cn = cn.replace(' ', '_')
                    auth["common-name"] = cn
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
        return conf_error(f"link is missing a name", block)
    if require_what not in ["authentication"]:
        return conf_error(f"Unknown require type: {require_what}", block)

    required = ["mask", "reason"]
    ok = 1
    for item in required:
        if not block.get_path(require_what + ':' + item):
            conf_error(f"Block '{block.name} {block.value}' is missing item '{item}'", block)
            ok = 0
    if ok:
        require_mask = Mask(block)
        Require(require_what, mask=require_mask, reason=block.get_single_value("reason"))


def config_test_alias(block):
    if not (alias_name := block.value):
        conf_error(f"alias is missing a name", block)
        return
    required = ["type"]
    ok = 1
    for item in required:
        if not block.get_path(item):
            conf_error(f"Block '{block.name} {block.value}' is missing item '{item}'", block)
            ok = 0

    if ok:
        alias = Alias(alias_name, block.get_single_value("type"))
        if target := block.get_single_value("target"):
            alias.target = target
        else:
            alias.target = alias.name

        if options := block.get_items("options"):
            for option in options:
                opt = option.get_single_value('options')
                alias.options.append(opt)


def config_test_except(block):
    if not (except_name := block.value):
        return conf_error(f"Except block is missing a name. Example: except tkl {{ ... }}", block)

    ok = 1
    required = ["mask"]
    missing_items = [item for item in required if not block.get_item(item)]
    if missing_items:
        conf_error(f"Block '{block.name} {block.value}' is missing item: {', '.join(missing_items)}", block)
        ok = 0

    # # Conf says ban types are optional.
    # if except_name == "ban" and not block.get_items("type"):
    #     conf_error(f"Block '{block.name} {block.value}' is missing required exception types.", block)
    #     ok = 0

    if ok:
        except_mask = Mask(block)
        types = []

        for type_item in block.get_items("type"):
            path = type_item.path
            type_what = path[2]
            if type_what not in ["kline", "gline", "zline", "gzline", "shun", "spamfilter", "dnsbl", "throttle", "require"]:
                conf_error(f"Invalid except:type: {type_what}", item=type_item)
                continue
            types.append(type_what)

        for mask_item in block.get_items("mask"):
            path = mask_item.path
            mask_what = path[2].removeprefix('.').removesuffix('.')
            mask_value = None
            if len(path[2:]) > 1:
                mask_value = path[3]
            full_mask = mask_item.path[2:]
            if not full_mask or not mask_what:
                continue

            if mask_value and mask_what not in except_mask.types:
                errmsg = f"Unrecognized mask type in except {block.name} {{ }} mask:{mask_what}. Valid: {', '.join(except_mask.types)}"
                conf_error(errmsg, item=mask_item)
                continue

            if mask_what in except_mask.types and not mask_value:
                errmsg = f"Missing value for except {block.name} {{ }} mask:{mask_what}"
                conf_error(errmsg, item=mask_item)
                continue

        e = Except(name=except_name, mask=except_mask, types=types)
        if comment := block.get_single_value("comment"):
            e.comment = comment


def config_test_ulines(block):
    ulines = []
    for entry in block.entries:
        server = entry.get_single_value().lower()
        if server in ulines:
            continue
        if server == IRCD.me.name.lower():
            conf_error(f"Invalid uline server: {server}. Cannot be this server!", block=block, item=entry)
            continue
        ulines.append(server)
    IRCD.set_setting("ulines", ulines)


def config_test_bans(block):
    if not (ban_type := block.value):
        conf_error(f"Ban block is missing a name. Example: ban nick {{ ... }}", block)
        return

    required = ["mask", "reason"]
    missing_items = [item for item in required if not block.get_item(item)]
    if missing_items:
        return conf_error(f"Block '{block.name} {block.value}' is missing item: {', '.join(missing_items)}", block)

    bans_mask = Mask(block)
    reason = block.get_single_value("reason")
    ban = Ban(ban_type=ban_type, mask=bans_mask, reason=reason)
