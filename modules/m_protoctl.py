"""
/protoctl command (server)
"""

import re
from time import time

from handle.core import IRCD, Command, Channelmode, Usermode, Isupport, Numeric
from classes.errors import Error
from handle.handleLink import deny_direct_link

from handle.logger import logging


@logging.client_context
def cmd_protoctl(client, recv):
    if len(recv) < 2:
        return

    current_time = int(time())
    try:
        for p in [p for p in recv[1:] if p not in client.local.protoctl]:
            try:
                cap = p.split('=')[0]

                if cap.upper() == "NAMESX":
                    client.set_capability("multi-prefix")
                    return
                elif cap.upper() == "UHNAMES":
                    client.set_capability("userhost-in-names")
                    return

                if client.user:
                    return client.sendnumeric(Numeric.ERR_SERVERONLY, "PROTOCTL")
                param = None
                client.local.protoctl.append(cap)
                if '=' in p:
                    param = p.split('=')[1]
                if cap == "EAUTH" and param:
                    name = param.split(',')[0]
                    # logging.debug(f"EAUTH name: {name}")
                    if (found := IRCD.find_client(name)) and found != client:
                        logging.warning(f"[EAUTH] Server with name {name} already exists.")
                        deny_direct_link(client, Error.SERVER_NAME_EXISTS, name)
                        return
                    client.name = name

                elif cap == "SID" and param:
                    if IRCD.find_client(param):  # and server_exists != client:
                        deny_direct_link(client, Error.SERVER_SID_EXISTS, param)
                        return
                    client.id = param
                    IRCD.client_by_id[client.id.lower()] = client
                    # logging.debug(f"[PROTOCTL] SID for {client.name} set: {client.id}")

                elif cap == "CHANMODES":
                    local_modes = IRCD.get_chmodes_str_categorized().replace(',', '')
                    remote_modes = param.replace(',', '')
                    local_missing = list(set(remote_modes).difference(set(local_modes)))
                    remote_missing = list(set(local_modes).difference(set(remote_modes)))
                    if remote_missing:
                        deny_direct_link(client, Error.SERVER_MISSING_CHANNELMODES, client.name, ', '.join(remote_missing))
                        return
                    modes_cat = param.split(',')
                    for mode in list(local_missing):
                        if mode in modes_cat[1:3]:
                            Channelmode.add_generic(mode, cat=modes_cat.index(mode) + 1)
                            local_missing.remove(mode)
                    if local_missing:
                        deny_direct_link(client, Error.SERVER_MISSING_CHANNELMODES, IRCD.me.name, ', '.join(local_missing))
                        return

                elif cap == "USERMODES":
                    local_umodes = Usermode.umodes_sorted_str()
                    remote_umodes = param
                    local_missing = list(set(remote_umodes).difference(set(local_umodes)))
                    remote_missing = list(set(local_umodes).difference(set(remote_umodes)))
                    if remote_missing:
                        msg = f"Remote server {client.name} is missing user modes: {', '.join(remote_missing)}"
                        IRCD.log(IRCD.me, "warn", "link", "LINK_MODES_MISMATCH", msg)
                    for mode in list(local_missing):
                        Usermode.add_generic(mode)
                        local_missing.remove(mode)
                    if local_missing:
                        deny_direct_link(client, Error.SERVER_MISSING_USERMODES, IRCD.me.name, ', '.join(local_missing))
                        return

                elif cap == "PREFIX":
                    local_membermodes = ''.join([m.flag for m in IRCD.channel_modes() if m.type == Channelmode.MEMBER])

                    if not (prefix_match := re.findall(r"\((\w+)\)", param)):
                        deny_direct_link(client, Error.SERVER_PROTOCTL_PARSE_FAIL, client.name, f"PROTOCTL {cap}={param}")
                        return

                    remote_membermodes = prefix_match[0]
                    local_missing = list(set(remote_membermodes).difference(set(local_membermodes)))
                    if local_missing:
                        deny_direct_link(client, Error.SERVER_MISSING_MEMBERMODES, IRCD.me.name, ", ".join(local_missing))
                        return

                elif cap == "EXTBAN":
                    remote_prefix = param[0]
                    remote_ban_types = param.split(',')[1]
                    local_prefix = (isupport := Isupport.get(cap)) and isupport.value[0]
                    if remote_prefix != local_prefix:
                        deny_direct_link(client, Error.SERVER_EXTBAN_PREFIX_MISMATCH, local_prefix, remote_prefix)
                        return

                    local_ban_types = isupport.value[2:]
                    missing_ext_types = []
                    for m in [m for m in remote_ban_types if m not in local_ban_types]:
                        missing_ext_types.append(m)
                    if missing_ext_types:
                        deny_direct_link(client, Error.SERVER_MISSING_EXTBANS, ', '.join(missing_ext_types))
                        return

                elif cap == "MTAGS":
                    client.set_capability("message-tags")

                elif cap == "VL":
                    # VL: Supports V:Line information.
                    # Extends the SERVER message to include version information.
                    client.local.protoctl.append("VL")

                elif cap == "TS":
                    remote_time = int(param)
                    diff = abs(remote_time - current_time)
                    if diff >= 30:
                        deny_direct_link(client, Error.SERVER_LINK_TS_MISMATCH, diff)
                        return

                    if diff >= 1 and client.name:
                        is_ahead = 1 if remote_time > current_time else 0
                        status = "ahead" if is_ahead else "behind"
                        msg = (f"*** (warning) Remote server {client.name}'s clock is ~{diff}s {status} on ours, "
                               f"this can cause issues and should be fixed!")
                        IRCD.log(client, level="warn", rootevent="link", event="LINK_WARNING_TS_MISMATCH", message=msg, sync=0)

            except Exception as ex:
                logging.exception(ex)
                client.exit(str(ex))

    except Exception as ex:
        logging.exception(ex)


def init(module):
    Command.add(module, cmd_protoctl, "PROTOCTL")
