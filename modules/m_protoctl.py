"""
/protoctl command (server)
"""
import re

from handle.core import Command, Flag, IRCD, Channelmode, Usermode, Isupport
from classes.errors import Error
from handle.handleLink import deny_direct_link

from handle.logger import logging


def cmd_protoctl(client, recv):
    # logging.warning(f"PROTOCTL from {client.name}: {recv}")
    try:
        for p in [p for p in recv[1:] if p not in client.local.protoctl]:
            try:
                cap = p.split('=')[0]
                param = None
                client.local.protoctl.append(cap)
                if '=' in p:
                    param = p.split('=')[1]
                if cap == 'EAUTH' and param:
                    name = param.split(',')[0]
                    logging.debug(f"EAUTH name: {name}")
                    if IRCD.find_server(name):  # and server_exists != client:
                        logging.warning(f"[EAUTH] Server with name {name} already exists.")
                        deny_direct_link(client, Error.SERVER_NAME_EXISTS, name)
                        return
                    client.name = name

                elif cap == 'SID' and param:
                    if IRCD.find_server(param):  # and server_exists != client:
                        deny_direct_link(client, Error.SERVER_SID_EXISTS, param)
                        return
                    client.id = param
                    logging.debug(f"[PROTOCTL] SID for {client.name} set: {client.id}")

                elif cap == 'CHANMODES':
                    local_modes = IRCD.get_chmodes_str_categorized().replace(',', '')
                    remote_modes = param.replace(',', '')
                    local_missing = list(set(remote_modes).difference(set(local_modes)))
                    remote_missing = list(set(local_modes).difference(set(remote_modes)))
                    if remote_missing:
                        msg = f"Server {client.name} is missing user modes: {', '.join(remote_missing)}"
                        IRCD.log(IRCD.me, "warn", "link", "LINK_MODES_MISMATCH", msg)
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
                        msg = f"Server {client.name} is missing user modes: {', '.join(remote_missing)}"
                        IRCD.log(IRCD.me, "warn", "link", "LINK_MODES_MISMATCH", msg)
                    for mode in list(local_missing):
                        Usermode.add_generic(mode)
                        local_missing.remove(mode)
                    if local_missing:
                        deny_direct_link(client, Error.SERVER_MISSING_USERMODES, IRCD.me.name, ', '.join(local_missing))
                        return

                elif cap == "PREFIX":
                    local_membermodes = ''.join([m.flag for m in IRCD.channel_modes() if m.type == Channelmode.MEMBER])
                    prefix_regex_find = re.findall(r"\((\w+)\)", param)
                    if not prefix_regex_find:
                        deny_direct_link(client, Error.SERVER_PROTOCTL_PARSE_FAIL, client.name, f"PROTOCTL {cap}={param}")
                        return
                    remote_membermodes = prefix_regex_find[0]
                    local_missing = list(set(remote_membermodes).difference(set(local_membermodes)))
                    if local_missing:
                        deny_direct_link(client, Error.SERVER_MISSING_MEMBERMODES, IRCD.me.name, ', '.join(local_missing))
                        return

                elif cap == 'EXTBAN':
                    remote_prefix = param[0]
                    remote_ban_types = param.split(',')[1]
                    local_prefix = None
                    if isupport := Isupport.get(cap):
                        local_prefix = isupport.value[0]
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
                    client.local.caps.append("message-tags")

                elif cap == "VL":
                    # VL : Supports V:Line information.
                    # Extends the SERVER message to include version information.
                    client.local.protoctl.append("VL")

            except Exception as ex:
                logging.exception(ex)
                client.exit(str(ex))

    except Exception as ex:
        logging.exception(ex)


def init(module):
    Command.add(module, cmd_protoctl, "PROTOCTL", 2, Flag.CMD_UNKNOWN)
