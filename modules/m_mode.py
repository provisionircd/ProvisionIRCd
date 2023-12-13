"""
/mode command
"""

from handle.core import Flag, Numeric, Channelmode, Isupport, Command, IRCD, Extban, Hook
from handle.functions import logging, make_mask

MAXMODES = 20


def show_channel_info(client, channel):
    if 's' in channel.modes and not channel.find_member(client) and not client.has_permission("channel:see:mode"):
        return
    show_params = []
    for m in channel.modes:
        if param := channel.get_param(m):
            show_params.append(param)
    client.sendnumeric(Numeric.RPL_CHANNELMODEIS, channel.name, channel.modes,
                       ' '.join(show_params) if show_params and (channel.find_member(client) or client.has_permission("channel:see:mode")) else '')
    client.sendnumeric(Numeric.RPL_CREATIONTIME, channel.name, channel.creationtime)


def cmd_usermode(client, recv):
    if not (target := IRCD.find_user(recv[1])):
        client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])
        return

    if len(recv) < 3:
        if target != client and 'o' not in client.user.modes:
            return
        return client.sendnumeric(Numeric.RPL_UMODEIS, target.user.modes)

    modes = recv[2]
    param = ''
    if len(recv) > 3:
        param = IRCD.strip_format(recv[3])
    modebuf = []
    action = '+'
    prevaction = ''
    unknown = []

    current_modes = target.user.modes
    current_snomask = target.user.snomask

    for mode in modes:
        if mode in "+-":
            action = mode
            continue

        if not (umode := IRCD.get_usermode_by_flag(mode)) and mode not in unknown:
            unknown.append(mode)
            continue

        oldumodes = target.user.modes

        if target != client:
            if client.user and not client.has_permission("client:set:usermode") and client.local:
                # Not authorized to change target user modes.
                client.sendnumeric(Numeric.ERR_USERSDONTMATCH)
                continue

        if not umode.can_set(client) and client.local:
            continue

        if action == "+":
            if mode not in target.user.modes:
                target.user.modes += mode
            if mode == 's' and target.user.oper and param:
                if param.startswith('-'):
                    for sno in [sno for sno in param if sno in target.user.snomask]:
                        target.user.snomask = target.user.snomask.replace(sno, '')
                else:
                    for sno in [sno for sno in param if sno in target.user.oper.snomasks and sno not in target.user.snomask]:
                        target.user.snomask += sno

        elif action == "-" and mode in target.user.modes:
            target.user.modes = target.user.modes.replace(mode, '')

        if target.user.modes != oldumodes:
            if action != prevaction:
                modebuf.append(action)
                prevaction = action
            modebuf.append(mode)

        if 'o' in set(oldumodes).difference(target.user.modes):
            if target.local:
                target.local.flood_penalty = 0
            # User de-opered. Also removing relevant oper modes.
            for opermode in [m for m in target.user.modes if IRCD.get_usermode_by_flag(m).unset_on_deoper]:
                target.user.modes = target.user.modes.replace(opermode, '')
                modebuf.append(opermode)
            target.user.snomask = target.user.snomask = ''

        if 's' in set(oldumodes).difference(target.user.modes):
            target.user.snomask = ''

        if 'x' in set(oldumodes).difference(target.user.modes):
            target.setinfo(info=target.user.realhost, t="host")
            data = f":{target.id} SETHOST :{target.user.cloakhost}"
            IRCD.send_to_servers(client, [], data)

        if 'x' in set(target.user.modes).difference(oldumodes):
            cloak = IRCD.get_cloak(target)
            target.setinfo(info=cloak, t="host")
            data = f":{target.id} SETHOST :{target.user.cloakhost}"
            IRCD.send_to_servers(client, [], data)

    if modebuf:
        # Broadcast buffer.
        mtags = []
        IRCD.new_message(client)
        modes = ''.join(modebuf)
        if target.local:
            data = f":{client.name} MODE {target.name} {modes}"
            target.send(mtags, data)

        sync_modes = ''
        for mode in modes:
            if mode in '+-':
                sync_modes += mode
                continue
            umode = IRCD.get_usermode_by_flag(mode)
            if umode and umode.is_global:
                sync_modes += mode
        data = f":{client.id} MODE {target.name} {sync_modes}"
        IRCD.send_to_servers(client, [], data)
        if target != client:
            client.sendnumeric(Numeric.RPL_OTHERUMODEIS, target.name, target.user.modes)

    if target.user.snomask != current_snomask and target.local:
        target.sendnumeric(Numeric.RPL_SNOMASK, target.user.snomask)

    IRCD.run_hook(Hook.UMODE_CHANGE, client, target, current_modes, target.user.modes, param)

    if unknown:
        client.sendnumeric(Numeric.ERR_UMODEUNKNOWNFLAG, ''.join(unknown))


def do_channel_member_mode(client, channel, action, mode, param):
    # logging.debug(f"[member] Client sets mode: {action}{mode} {param} on {channel.name}")
    if not (target_client := IRCD.find_user(param)):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, param)
    if target_client not in channel.clients():
        return client.sendnumeric(Numeric.ERR_USERNOTINCHANNEL, param, channel.name)
    if action == '+':
        if channel.client_has_membermodes(target_client, mode):
            return 0
        channel.member_give_modes(target_client, mode)
        return 1
    elif action == '-':
        if not channel.client_has_membermodes(target_client, mode):
            return 0
        channel.member_take_modes(target_client, mode)
        return 1
    return 0


def add_to_buff(modebuf, parambuf, action, prevaction, mode, param):
    # logging.debug(f"Adding {action}{mode} to modebuf")
    if action != prevaction:
        modebuf.append(action)
        prevaction = action
    modebuf.append(mode)
    if param:
        parambuf.append(str(param))
    return prevaction


def handle_mode_list(client, channel, action, mode, param):
    """
    At this point the user already has permission to set bans etc.
    They require +h and this is being checked on early in the /MODE command.
    """

    param_mask = make_mask(param)
    use_list = channel.List[mode]
    if param.startswith(Extban.symbol):
        param = Extban.convert_param(param, convert_to_name=1)

    if action == '+':
        extban_valid = Extban.is_extban(client, channel, action, mode, param)
        if extban_valid == -1:
            # Extban format received but was not valid, don't process.
            return
        elif extban_valid != 0:
            param_mask = extban_valid

    if action == "+" and not channel.mask_in_list(param_mask, use_list):
        channel.add_to_list(client, param_mask, use_list)
        return param_mask
    elif action == "-" and (channel.mask_in_list(param_mask, use_list) or channel.mask_in_list(param, use_list)):
        if entry_mask := channel.remove_from_list([param, param_mask], use_list):
            return entry_mask
        return param_mask


def display_channel_list_entries(client, channel, mode):
    list_modes = IRCD.get_list_modes_str()
    for char in mode:
        if char in list_modes:
            mode = char
    if mode in list_modes:
        if not channel.find_member(client) and not client.has_permission("channel:see:banlist"):
            client.sendnumeric(Numeric.ERR_NOTONCHANNEL, channel.name)
            return 1
        for result, callback in Hook.call(Hook.CHAN_LIST_ENTRY, args=(client, channel, mode)):
            if result == 1:
                # Success.
                return 1

    return 0


def send_modelines(client, channel, modebuf, parambuf, send_ts=0):
    def send_one_line():
        server_params = []
        for param in params_out:
            param_split = param.split(':')
            if len(param_split) > 1:
                if cparam := Extban.convert_param(param, convert_to_name=0):
                    server_params.append(cparam)
                continue
            server_params.append(param)

        if client == IRCD.me or client.server:
            server_params.append(str(send_ts))

        send_string = f"{modes_out}{' ' + ' '.join(params_out) if params_out else ''}"
        data = f":{client.name} MODE {channel.name} {send_string}"
        channel.broadcast(client, data)

        if channel.name[0] != '&':
            server_send_string = f"{modes_out}{' ' + ' '.join(server_params) if server_params else ''}"
            data = f":{client.id} MODE {channel.name} {server_send_string}"
            IRCD.send_to_servers(client, mtags=client.mtags, data=data)

    modes_out = ''
    params_out = []
    action = ''
    paramcount = 0
    parammode_count = 0
    for mode in modebuf:
        if mode in ['+', '-']:
            action = mode
            modes_out += action
            continue
        if not (cmode := IRCD.get_channelmode_by_flag(mode)):
            continue
        modes_out += mode
        if mode in IRCD.get_parammodes_str():
            if (action == '-' and cmode.unset_with_param) or action == '+':
                params_out.append(parambuf[paramcount])
                paramcount += 1
                parammode_count += 1
        total_len = len(''.join(modes_out) + ' ' + ' '.join(params_out))
        if parammode_count == MAXMODES or total_len > 500:
            send_one_line()
            modes_out = action
            params_out = []
            parammode_count = 0
    if modes_out:
        send_one_line()

    hook = Hook.LOCAL_CHANNEL_MODE if client == IRCD.me or client.local else Hook.REMOTE_CHANNEL_MODE
    IRCD.run_hook(hook, client, channel, modebuf, parambuf)


def cmd_channelmode(client, recv):
    channel = IRCD.find_channel(recv[1])
    if len(recv) == 2:
        # Requesting channel info.
        return show_channel_info(client, channel)

    if len(recv) == 3 and display_channel_list_entries(client, channel, recv[2]):
        return

    override = 0
    if client.user and not channel.client_has_membermodes(client, "hoaq"):
        if client.local and not client.has_permission("channel:override:mode"):
            return client.sendnumeric(Numeric.ERR_CHANOPRIVSNEEDED, channel.name)
        else:
            override = 1

    # https://gist.github.com/jlu5/5233ebe64d5c8c1f079ef8c8fcb759ff#55-mode---channel-mode-token-g
    send_ts = 0
    if client.server:
        if not recv[-1].isdigit() or int(recv[-1]) <= 1_500_000:
            send_ts = channel.creationtime

        send_ts = int(send_ts)
        if not send_ts and recv[-1] != '0':
            send_ts = channel.creationtime

        elif send_ts > 0:
            if client != IRCD.me:
                if send_ts < channel.creationtime:
                    channel.creationtime = send_ts
                    logging.warning(f"[SEND_TS] Local channel {channel.name} timestamp changed to: {channel.creationtime}")
                    data = f":{IRCD.me.id} MODE {channel.name} + {channel.creationtime}"
                    IRCD.send_to_servers(client, [], data)
                elif send_ts > channel.creationtime and channel.creationtime:
                    send_ts = channel.creationtime
                    logging.warning(f"[SEND_TS] Remote server channel {channel.name} timestamp is wrong")
                    data = f":{IRCD.me.id} MODE {channel.name} + {channel.creationtime}"
                    client.direction.send([], data)
                """
                Removing timestamp from params.
                """
                recv = recv[:-1]
                logging.warning(f"Removing extra param (TS) from recv: {send_ts}")
                """"""

            else:
                send_ts = channel.creationtime

    modes = recv[2]
    params = []
    if len(recv) > 3:
        params = recv[3:]
    action = '+'
    prevaction = ''
    paramcount = 0
    modebuf = []
    parambuf = []
    unknown = []
    param_modes = [c.flag for c in Channelmode.table if c.paramcount and not c.unset_with_param]
    # +vhoaq and +kL
    param_modes_unset = [c.flag for c in Channelmode.table if c.paramcount and c.unset_with_param]

    for mode in modes:
        param = None
        if mode in "+-":
            action = mode
            continue
        if not (cmode := IRCD.get_channelmode_by_flag(mode)):
            unknown.append(mode)
            continue

        if cmode.is_ok == Channelmode.allow_none:
            if not client.server and client.local:
                continue

        if mode in IRCD.get_list_modes_str():
            if len(params) <= paramcount:
                continue
            param = params[paramcount]
            param = IRCD.strip_format(param)
            paramcount += 1
            if returned_param := handle_mode_list(client, channel, action, mode, param):
                prevaction = add_to_buff(modebuf, parambuf, action, prevaction, mode, returned_param)
            continue

        if client.user:
            allowed = cmode.is_ok(client, channel, action, mode, param, cmode.CHK_ACCESS) or not client.local
            if not allowed and client.has_permission("channel:override:mode"):
                override = 1
            elif not allowed:
                if allowed == 0:
                    client.sendnumeric(Numeric.ERR_CHANOPRIVSNEEDED, channel.name)
                continue

        if client.user and client.local and not client.has_permission("channel:override:mode"):
            for callback, result in Hook.call(Hook.PRE_LOCAL_CHANNEL_MODE, args=(client, channel, modebuf, parambuf, action, mode, param)):
                if result == Hook.DENY:
                    continue

        oldcmodes = channel.modes
        if mode not in param_modes + param_modes_unset:
            if action == "+" and mode not in channel.modes:
                channel.modes += mode
            elif action == "-" and mode in channel.modes:
                channel.modes = channel.modes.replace(mode, '')

        elif mode in param_modes:
            # These modes require param on set, but not on unset.
            # Such as limit, +l
            if action == '+':
                if len(params) <= paramcount:
                    continue
                param = params[paramcount]
                param = IRCD.strip_format(param)
                paramcount += 1

                if result := cmode.is_ok(client, channel, action, mode, param, cmode.CHK_PARAM) or not client.local:
                    logging.debug(f"Allowed to {action}{mode} {param}: {result} by {cmode.is_ok}")
                    if not (param := str(cmode.conv_param(param))) and not client.local:
                        # Param not allowed.
                        continue
                    channel.add_param(mode, param)
                    if mode not in channel.modes:
                        channel.modes += mode
                    else:
                        # These modes are special as you can + them to change their parameter.
                        # But if the mode is already set, code below won't trigger the modebuf append so we do it here.
                        prevaction = add_to_buff(modebuf, parambuf, action, prevaction, mode, param)

            elif action == '-':
                if mode in channel.modes:
                    channel.modes = channel.modes.replace(mode, '')
                    if channel.get_param(mode):
                        channel.del_param(mode)

        elif mode in param_modes_unset:
            if len(params) <= paramcount:
                continue
            # These modes require param on set, but also on unset.
            param = params[paramcount]
            param = IRCD.strip_format(param)
            paramcount += 1
            if cmode.type == cmode.MEMBER:
                if do_channel_member_mode(client, channel, action, mode, param):
                    nick = IRCD.find_user(param).name
                    prevaction = add_to_buff(modebuf, parambuf, action, prevaction, mode, param=nick)
                continue

            if not cmode.is_ok(client, channel, action, mode, param, cmode.CHK_PARAM) and client.local:
                continue

            if client.local:
                if not (param := str(cmode.conv_param(param))):
                    # Param not allowed.
                    continue

            if action == '+':
                if mode not in channel.modes:
                    channel.modes += mode
                    channel.add_param(mode, param)

            elif action == '-':
                if mode in channel.modes and param == channel.get_param(mode):
                    channel.modes = channel.modes.replace(mode, '')
                    channel.del_param(mode)

        if channel.modes != oldcmodes:
            # Modes changed. Add to buffer.
            prevaction = add_to_buff(modebuf, parambuf, action, prevaction, mode, param)

    if modebuf:
        # Broadcast buffer.
        send_modelines(client, channel, modebuf, parambuf, send_ts)

        if override and not client.ulined and client.user:
            modes_set = ''.join(modebuf)
            params_set = ' '.join(parambuf)
            mode_string = f"{modes_set}{' ' + params_set if parambuf else ''}"
            override_string = f"*** OperOverride by {client.name} ({client.user.username}@{client.user.realhost}) with MODE {channel.name} {mode_string}"
            IRCD.log(client, "info", "oper", "OPER_OVERRIDE", override_string, sync=0)

    if unknown and client.user:
        client.sendnumeric(Numeric.ERR_UNKNOWNMODE, ''.join(unknown))


def cmd_mode(client, recv):
    target = recv[1]
    if IRCD.find_channel(target):
        cmd_channelmode(client, recv)
    elif IRCD.find_user(target):
        cmd_usermode(client, recv)


def cmd_samode(client, recv):
    if not client.has_permission("sacmds:samode"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
    if not IRCD.find_channel(recv[1]):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv[1])
    Command.do(IRCD.me, "MODE", *recv[1:])


def init(module):
    Command.add(module, cmd_mode, "MODE", 1, Flag.CMD_USER)
    Command.add(module, cmd_samode, "SAMODE", 2, Flag.CMD_OPER)
    Isupport.add("MODES", MAXMODES)
