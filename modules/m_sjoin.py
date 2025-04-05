"""
/sjoin command (server)
"""

import time
import re

from handle.core import IRCD, Command
from classes.data import Extban, Flag, Isupport, Hook
from handle.logger import logging
from modules.ircv3.batch import Batch


def get_users_from_memberlist(memberlist: list) -> list:
    user_prefixes = [m.sjoin_prefix for m in IRCD.channel_modes() if m.type == m.MEMBER]
    list_prefixes = [m.sjoin_prefix for m in IRCD.channel_modes() if m.type == m.LISTMODE]

    users = []
    for entry in memberlist:
        if entry[0] == '<' and (match := re.match(r"<(.*),(.*)>(.*)", entry)):
            entry = match.groups()[2]

        user_uid = ''
        for char in entry:
            if char in list_prefixes:
                # Not interested in those.
                break
            if char not in user_prefixes:
                user_uid += char

        if user_uid and (user := IRCD.find_client(user_uid)):
            users.append(user)

    return users


@logging.client_context
def get_usermodes_from_memberlist(remote_server, memberlist: list) -> list:
    usermodes = []
    known_user_prefixes = [m.sjoin_prefix for m in IRCD.channel_modes() if m.sjoin_prefix and m.type == m.MEMBER]
    for entry in memberlist:
        if not entry or entry[0] == '<':
            continue

        modes = ''
        user_uid = ''
        for char in entry:
            if char in known_user_prefixes and (cmode := next((cm for cm in IRCD.channel_modes() if cm.sjoin_prefix == char), 0)):
                modes += cmode.flag
            else:
                user_uid += char

        if user_uid and (user := IRCD.find_client(user_uid)):
            if user.name == '*':
                # How the fuck...?
                logging.error(f"Found remote user without nickname. UID command without nickname received?")
                continue
            usermodes.append((user, modes))
    return usermodes


@logging.client_context
def get_listmodes_from_memberlist(remote_server, memberlist: list) -> (list, list):
    known_list_prefixes = [m.sjoin_prefix for m in IRCD.channel_modes() if m.sjoin_prefix and m.type == m.LISTMODE]
    listmodes_modebuf, listmodes_parambuf = [], []
    timestamp = int(time.time())
    setter = remote_server.name

    for entry in memberlist:
        if entry[0] == '<':
            if not (match := re.match(r"<(.*),(.*)>(.*)", entry)):
                logging.error(f"Malformed SJSBY format received: {entry} -- skipping entry.")
                IRCD.send_snomask(remote_server, 's', f"ERROR: Malformed SJSBY format received: "
                                                      f"{entry} -- some channel modes may not have been synced correctly!")
                continue
            timestamp, setter, entry = match.groups()

        for char in entry:
            if char in known_list_prefixes:
                if cmode := next((cm for cm in IRCD.channel_modes() if cm.sjoin_prefix == char), 0):
                    listmodes_modebuf.append(cmode.flag)
                    listmodes_parambuf.append((timestamp, setter, entry[1:]))

    return listmodes_modebuf, listmodes_parambuf


def do_normal_join(server_client, channel_object, memberlist: list) -> None:
    """ Join all remote members from memberlist to local channel. """
    for user in get_users_from_memberlist(memberlist):
        IRCD.new_message(user)
        # Remove msgid tag because it won't be the same across the network.
        mtags = server_client.recv_mtags if server_client.server.synced else [t for t in user.mtags if t.name != "msgid"]
        channel_object.do_join(mtags, user)
        IRCD.run_hook(Hook.REMOTE_JOIN, user, channel_object)
        user.mtags = []


def send_modelines(server, channel_object, modebuf: list, parambuf: list, action: str) -> None:
    maxmodes = Isupport.get("MODES").value if Isupport.get("MODES") else 8
    modes_out, params_out = [], []
    paramcount = 0

    def send_one_line() -> None:
        modebuf_string = ''.join(modes_out)
        parambuf_string = ' '.join(params_out) if params_out else ''
        data = f":{server.name} MODE {channel_object.name} {action}{modebuf_string}{' ' + parambuf_string if parambuf_string else ''}"
        for client in [c for c in channel_object.clients() if c.local]:
            Batch.check_batch_event(mtags=client.mtags, started_by=server, target_client=client, event="netjoin")
            client.send(client.mtags, data)
            client.mtags = []

    for mode in [m for m in modebuf if m not in "+-"]:
        cmode = IRCD.get_channelmode_by_flag(mode)
        modes_out.append(mode)
        if mode in IRCD.get_parammodes_str():
            if ((action == '-' and cmode.unset_with_param) or action == '+') and len(parambuf) > paramcount:
                param = parambuf[paramcount]
                params_out.append(param)
                paramcount += 1

        total_len = len(''.join(modes_out) + ' ' + ' '.join(params_out))
        if len(modes_out) >= maxmodes or total_len > 400:
            send_one_line()
            modes_out, params_out = [], []

    if modes_out:
        send_one_line()


def handle_modes(channel_object, remote_modes: str, remote_params: list, action: str, common_modes=None) -> tuple:
    if common_modes is None:
        common_modes = {}

    modebuf = []
    parambuf = []
    paramcount = 0

    for mode in remote_modes:
        if not (cmode := IRCD.get_channelmode_by_flag(mode)):
            continue

        if action == '-' and mode in common_modes and mode not in IRCD.get_parammodes_str():
            continue

        if mode in IRCD.get_parammodes_str() and len(remote_params) > paramcount:
            """
            Handling the param modes like +k and +l, etc.
            """

            param, ourparam = remote_params[paramcount], channel_object.get_param(mode)
            paramcount += 1

            if mode in channel_object.modes and param == ourparam:
                continue

            if action == '+':
                if mode not in channel_object.modes:
                    channel_object.modes += mode
                if (ourparam and cmode.sjoin_check(ourparam, param) == -1) or not ourparam:
                    modebuf.append(mode)
                    parambuf.append(param)
                    channel_object.add_param(mode, param)

            elif action == '-':
                channel_object.modes = channel_object.modes.replace(mode, '')
                modebuf.append(mode)
                parambuf.append(ourparam)
                channel_object.del_param(mode)

        else:
            """
            Now we handle the normal non-param modes, like +n and +t, etc.
            """

            if action == '+' and mode not in channel_object.modes:
                channel_object.modes += mode
                modebuf.append(mode)

            elif action == '-' and mode in channel_object.modes:
                channel_object.modes = channel_object.modes.replace(mode, '')
                modebuf.append(mode)

    return modebuf, parambuf


@logging.client_context
def set_remote_modes(remote_server, channel_object, remote_modes: str, remote_params: list, memberlist: list) -> None:
    remote_modes = remote_modes.replace('+', '')
    modebuf_give, parambuf_give = handle_modes(channel_object, remote_modes, remote_params, action='+')
    channel_object.modes = remote_modes

    # +vhoaq etc.
    usermodes = get_usermodes_from_memberlist(remote_server, memberlist)
    for entry in usermodes:
        client, modes = entry
        if channel_object.create_member(client):
            channel_object.member_give_modes(client, modes)
            for mode in modes:
                modebuf_give.append(mode)
                parambuf_give.append(client.name)
        else:
            logging.error(f"[set_remote_modes()] Attempted to join {client.name} to {channel_object.name} but it already exists.")

    # Join remote users to channel.
    do_normal_join(remote_server, channel_object, memberlist)

    # Now merge/update listmodes.
    listmodes_modebuf, listmodes_parambuf = get_listmodes_from_memberlist(remote_server, memberlist)
    for listmode, listparam in zip(listmodes_modebuf, listmodes_parambuf):
        timestamp, setter, mask = listparam
        if mask.startswith(Extban.symbol):
            mask = Extban.convert_param(mask, convert_to_name=1)
        channel_object.add_to_list(remote_server, mask=mask, _list=channel_object.List[listmode], setter=setter, timestamp=timestamp)
        modebuf_give.append(listmode)
        parambuf_give.append(mask)

    send_modelines(remote_server, channel_object, modebuf_give, parambuf_give, action='+')


def remote_wins(remote_server, channel_object, remote_modes: str, remote_params: list,
                memberlist: list, remote_channel_creation: int) -> None:
    common_modes = set(channel_object.modes) & set(remote_modes)
    modebuf_remove, parambuf_remove = handle_modes(channel_object, channel_object.modes, remote_params,
                                                   action='-', common_modes=common_modes)

    # Now remove +vhoaq etc.
    for client in channel_object.member_by_client:
        if member_modes := channel_object.get_membermodes_sorted(client=client):
            modes = ''.join(mode.flag for mode in member_modes)
            modebuf_remove.extend(modes)
            parambuf_remove.extend([client.name] * len(modes))
            channel_object.member_take_modes(client, modes)

    # Remove bans etc.
    for listmode, entries in channel_object.List.items():
        for entry in entries:
            modebuf_remove.append(listmode)
            parambuf_remove.append(entry.mask)

    channel_object.init_lists()
    channel_object.creationtime = remote_channel_creation
    send_modelines(remote_server, channel_object, modebuf_remove, parambuf_remove, action='-')

    # Now give remote modes to local channel.
    set_remote_modes(remote_server, channel_object, remote_modes, remote_params, memberlist)


@logging.client_context
def merge_modes(remote_server, channel_object, remote_modes: str, remote_params: list, memberlist: list) -> None:
    merge_modebuf, merge_parambuf = handle_modes(channel_object, remote_modes, remote_params, action='+')

    # +vhoaq etc.
    for client, modes in get_usermodes_from_memberlist(remote_server, memberlist):
        if channel_object.create_member(client):
            channel_object.member_give_modes(client, modes)
            for mode in modes:
                merge_modebuf += mode
                merge_parambuf.append(client.name)
        else:
            logging.error(f"[merge_modes()] Attempted to join {client.name} to {channel_object.name} but it already exists.")

    # Join remote users to channel.
    do_normal_join(remote_server, channel_object, memberlist)

    # Merge/update listmodes.
    listmodes_modebuf, listmodes_parambuf = get_listmodes_from_memberlist(remote_server, memberlist)
    for listmode, listparam in zip(listmodes_modebuf, listmodes_parambuf):
        timestamp, setter, mask = listparam
        timestamp = int(timestamp)
        found = next((e for e in channel_object.List[listmode] if e.mask == mask), None)
        if found:
            if found.set_time > timestamp:
                found.set_time, found.setter = timestamp, setter
        else:
            channel_object.add_to_list(remote_server, mask, channel_object.List[listmode], setter, timestamp)
            merge_modebuf += listmode
            merge_parambuf.append(mask)

    send_modelines(remote_server, channel_object, merge_modebuf, merge_parambuf, action='+')


@logging.client_context
def cmd_sjoin(client, recv: list) -> None:
    channel_name = recv[2]
    if channel_name[0] == '&':
        logging.error(f"ERROR: received a local channel: {channel_name}")
        msg = f"Link failed for {client.name}: Sync error! Server {client.name} tried to link local channels!"
        client.direct_send(f"ERROR :{msg}")
        return client.exit(msg)

    if not (channel_object := IRCD.find_channel(channel_name)):
        channel_object = IRCD.create_channel(IRCD.me, channel_name)

    remote_channel_creation = int(recv[1])
    channel_object.remote_creationtime = channel_object.remote_creationtime or remote_channel_creation

    channel_modes = ''
    channel_modes_params = []
    memberlist = []

    for idx, param in enumerate(recv[3:], 3):
        if param.startswith(':'):
            memberlist = [p[1:] if i == idx else p for i, p in enumerate(recv[idx:], idx)]
            if not memberlist[0].strip():
                del memberlist[0]
            break
        channel_modes = param if not channel_modes else channel_modes
        channel_modes_params.append(param) if channel_modes != param else None

    # Start our netjoin batch, if one doesn't already exist.
    if not client.server.synced and not Batch.find_batch_by(client.direction):
        Batch.create_new(started_by=client.direction, batch_type="netjoin", additional_data=client.name + ' ' + client.uplink.name)

    # Force merge trigger, debug.
    # remote_channel_creation = channel_object.creationtime
    # channel_object.local_creationtime = remote_channel_creation
    # channel_object.remote_creationtime = remote_channel_creation

    if remote_channel_creation < channel_object.creationtime:
        # Remote channel is dominant. Replacing modes with remote channel. Clear the local modes.
        # logging.debug(f"Remote channel {channel_name} is dominant, clearing local channel modes and setting theirs.")
        channel_object.name = channel_name
        remote_wins(client, channel_object, channel_modes, channel_modes_params, memberlist, remote_channel_creation)

    elif remote_channel_creation > channel_object.creationtime:
        # Do nothing, our channel state will remain untouched.
        # logging.debug(f"Local channel {channel_name} is dominant. Not processing remote modes. Joining users.")
        do_normal_join(client, channel_object, memberlist)

    elif remote_channel_creation == channel_object.creationtime:
        merge_modes(client, channel_object, channel_modes, channel_modes_params, memberlist)

    if not client.registered:
        IRCD.run_hook(Hook.SERVER_SJOIN_IN, client, recv)


def init(module) -> None:
    Command.add(module, cmd_sjoin, "SJOIN", 4, Flag.CMD_SERVER)
