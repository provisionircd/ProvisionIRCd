"""
/mode command
"""

from handle.core import IRCD, Command, Channelmode, Usermode, Hook, Flag, Numeric, Isupport
from classes.data import Extban
from handle.logger import logging
from handle.functions import make_mask

# Maximum modes to process with a single MODE command.
# Modes exceeding this number will be processed on multiple lines.
MAXMODES = 20


def get_new_modes(current_modes, modes):
    # Use a dictionary to track the final action for each mode
    final_actions = {}
    action = '+'

    # Step 1: Track the final action for each mode
    for mode in modes:
        if mode in "+-":
            action = mode
            continue

        if not IRCD.get_usermode_by_flag(mode):
            continue

        # Record the most recent action for this mode
        final_actions[mode] = action

    # Step 2: Apply final actions against current modes
    additions = set()
    removals = set()

    for mode, action in final_actions.items():
        if action == '+' and mode not in current_modes:
            additions.add(mode)
        elif action == '-' and mode in current_modes:
            removals.add(mode)

    # Step 3: Build the final mode string
    new_modes = ''
    if additions:
        new_modes += '+' + ''.join(sorted(additions))
    if removals:
        new_modes += '-' + ''.join(sorted(removals))

    return new_modes


def show_channel_info(client, channel):
    can_see = channel.find_member(client) or client.has_permission("channel:see:mode")
    if all(m in channel.modes for m in ['s', 'p']) and not can_see:
        return

    show_params = ' '.join([p for m in channel.modes if (p := channel.get_param(m))]) if can_see else ''
    client.sendnumeric(Numeric.RPL_CHANNELMODEIS, channel.name, channel.modes, show_params)
    client.sendnumeric(Numeric.RPL_CREATIONTIME, channel.name, channel.creationtime)


def cmd_usermode(client, recv):
    if not (target := IRCD.find_client(recv[1], user=1)):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

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

    oper_warn = 0

    if not (modes := get_new_modes(current_modes, modes)):
        return

    for idx, mode in enumerate(modes):
        if mode in "+-":
            action = mode
            continue

        if idx > 0 and modes[idx - 1] == mode or not (umode := IRCD.get_usermode_by_flag(mode)):
            unknown.append(mode) if mode not in unknown else None
            continue

        can_set = umode.can_set(client) or client.has_flag(Flag.CLIENT_CMD_OVERRIDE)
        oldumodes = target.user.modes

        if target != client:
            if not client.has_permission("client:set:usermode"):
                # Not authorised to change target user modes.
                client.sendnumeric(Numeric.ERR_USERSDONTMATCH)
                continue

        if action == '+':
            if mode != 's' and mode in target.user.modes:
                # Snomasks can be changed by +s <snomasks>.
                continue
            if not can_set:
                if (client.is_local_user() and ('o' in client.user.modes and client.user.oper)
                        and umode.can_set == Usermode.allow_opers and not oper_warn):
                    client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
                    oper_warn = 1
                continue

            if mode not in target.user.modes:
                target.user.modes += mode

            # Handle snomasks.
            if mode == 's' and param and (target.user.oper or client.has_flag(Flag.CLIENT_CMD_OVERRIDE)):
                sno_action = '+'
                for sno in [s for s in param if s in "+-" or IRCD.get_snomask(s)]:
                    if sno in "+-":
                        sno_action = sno
                        continue
                    if sno_action == '-' and sno in target.user.snomask:
                        target.user.snomask = target.user.snomask.replace(sno, '')
                    elif sno_action == '+' and sno not in target.user.snomask:
                        if (target.user.oper and sno in target.user.oper.snomasks) or client.has_flag(Flag.CLIENT_CMD_OVERRIDE):
                            target.user.snomask += sno

        elif action == '-' and mode in target.user.modes:
            if not can_set:
                continue
            if mode in IRCD.get_setting("modelock") and not client.has_permission("self:override:modelock"):
                client.sendnumeric(Numeric.ERR_CANNOTCHANGEUMODE, mode, "This mode is locked")
                continue

            if mode in target.user.modes:
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

        if 's' in set(oldumodes).difference(target.user.modes):
            target.user.snomask = ''

    if modebuf:
        action = ''
        for mode in modebuf:
            if mode in "+-":
                action = mode
            elif action:
                hook = Hook.UMODE_SET if action == '+' else Hook.UMODE_UNSET
                IRCD.run_hook(hook, client, target, modebuf, mode)

        def apply_mode_changes(modebuf, user_modes):
            # Re-check modebuf again for changes, apply when needed.
            action = '+'
            for mode in modebuf:
                if mode in '+-':
                    action = mode
                    continue

                if action == '+' and mode not in user_modes:
                    user_modes += mode
                elif action == '-' and mode in user_modes:
                    user_modes = user_modes.replace(mode, '')

            return user_modes

        target.user.modes = apply_mode_changes(modebuf, target.user.modes)

        modes = ''.join(modebuf)
        if target.local:
            target.send([], f":{client.name} MODE {target.name} {modes}")

        sync_modes = ''
        for mode in modes:
            if mode in "+-" or (umode := IRCD.get_usermode_by_flag(mode)) and umode.is_global:
                sync_modes += mode

        IRCD.send_to_servers(client, [], f":{client.id} MODE {target.name} {sync_modes}")

        if target != client:
            client.sendnumeric(Numeric.RPL_OTHERUMODEIS, target.name, target.user.modes)

        IRCD.run_hook(Hook.UMODE_CHANGE, client, target, current_modes, target.user.modes)

    if target.user.snomask != current_snomask and target.local:
        target.sendnumeric(Numeric.RPL_SNOMASK, target.user.snomask)

    if unknown:
        client.sendnumeric(Numeric.ERR_UMODEUNKNOWNFLAG, ''.join(unknown))


def do_channel_member_mode(client, channel, action, mode, param):
    if not (target_client := IRCD.find_client(param, user=1)):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, param)
    if not channel.find_member(target_client):
        return client.sendnumeric(Numeric.ERR_USERNOTINCHANNEL, param, channel.name)
    if action == '+' and not channel.client_has_membermodes(target_client, mode):
        channel.member_give_modes(target_client, mode)
        return 1
    elif action == '-' and channel.client_has_membermodes(target_client, mode):
        channel.member_take_modes(target_client, mode)
        return 1
    return 0


def add_to_buff(modebuf, parambuf, action, prevaction, mode, param):
    if action != prevaction:
        modebuf.append(action)
    modebuf.append(mode)
    if param:
        parambuf.append(str(param))
    return action


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

    if action == '+' and not channel.mask_in_list(param_mask, use_list):
        cmode = IRCD.get_channelmode_by_flag(mode)

        if (not cmode.is_ok(client, channel, action, mode, param, cmode.CHK_ACCESS)
                or not cmode.is_ok(client, channel, action, mode, param, cmode.CHK_PARAM)):
            return

        channel.add_to_list(client, param_mask, use_list)
        return param_mask

    elif action == '-' and (channel.mask_in_list(param_mask, use_list) or channel.mask_in_list(param, use_list)):
        if entry_mask := channel.remove_from_list([param, param_mask], use_list):
            return entry_mask

        return param_mask


def display_channel_list_entries(client, channel, mode):
    if client == IRCD.me:
        return 0

    list_modes = IRCD.get_list_modes_str() + "aq"

    for char in mode:
        if char in list_modes:
            mode = char
    if mode in list_modes:
        if not channel.find_member(client) and not client.has_permission("channel:see:banlist"):
            client.sendnumeric(Numeric.ERR_NOTONCHANNEL, channel.name)
            return 1

        for result, callback in Hook.call(Hook.CHAN_LIST_ENTRY, args=(client, channel, mode)):
            if result == 1:
                return 1

    return 0


def send_modelines(client, channel, modebuf, parambuf, send_ts=0):
    def send_one_line():
        IRCD.new_message(client)
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
        channel.broadcast(client, f":{client.name} MODE {channel.name} {send_string}")

        if channel.name[0] != '&':
            server_send_string = f"{modes_out}{' ' + ' '.join(server_params) if server_params else ''}"
            data = f":{client.id} MODE {channel.name} {server_send_string}"
            IRCD.send_to_servers(client, mtags=client.mtags, data=data)

    modes_out = ''
    params_out = []
    action = ''
    paramcount = 0
    for mode in modebuf:
        if mode in "+-":
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
        modes_count = len(''.join(modes_out).replace('+', '').replace('-', ''))
        total_len = modes_count + len(params_out)
        if modes_count == MAXMODES or total_len > 510:
            send_one_line()
            modes_out = ''
            params_out = []
    if modes_out:
        send_one_line()

    hook = Hook.LOCAL_CHANNEL_MODE if client == IRCD.me or client.local else Hook.REMOTE_CHANNEL_MODE
    IRCD.run_hook(hook, client, channel, modebuf, parambuf)


@logging.client_context
def process_channel_timestamp(client, channel, recv):
    """
    Process channel mode timestamps following UnrealIRCd's logic.

    Returns:
        tuple: (send_ts, ts_change, should_continue)
            - send_ts: Timestamp to include in outgoing messages
            - ts_change: Boolean indicating if our timestamp changed
            - should_continue: 0 if mode processing should be aborted
    """
    send_ts = 0
    ts_change = 0

    if not (len(recv) > 2 and str(recv[-1]).isdigit()):
        return send_ts, ts_change, 1

    timestamp = int(recv[-1])

    if not client.server or timestamp <= 0:
        return send_ts, ts_change, 1

    if client != IRCD.me and not client.is_uline() and timestamp > channel.creationtime:
        msg = (f"Dropping MODE from server {client.name} for channel {channel.name}: "
               f"their timestamp={timestamp}, ours={channel.creationtime}")
        IRCD.log(client, "warn", "mode", "MODE_TS_IGNORED", message=msg)
        return send_ts, ts_change, 0

    if timestamp < channel.creationtime:
        ts_change = 1
        old_ts = channel.creationtime
        channel.creationtime = timestamp
        send_ts = timestamp
        logging.warning(f"Channel {channel.name} timestamp updated from {old_ts} to {timestamp}")
        msg = f"Updated {channel.name} timestamp from {old_ts} to {timestamp}"
        IRCD.log(client, "warn", "mode", "MODE_TS_UPDATED", message=msg)

    # Their timestamp is later than ours - send a correction
    elif timestamp > channel.creationtime > 0:
        client.send([], f":{IRCD.me.name} MODE {channel.name} + {channel.creationtime}")
        send_ts = channel.creationtime

    # Special case - if sendts is -1 in the original code
    elif timestamp == -1:
        send_ts = channel.creationtime

    recv.pop()

    return send_ts, ts_change, 1


def cmd_channelmode(client, recv):
    channel = IRCD.find_channel(recv[1])
    if len(recv) == 2:
        return show_channel_info(client, channel)

    if len(recv) == 3 and display_channel_list_entries(client, channel, recv[2]):
        return

    override = 0
    if client.user and not channel.client_has_membermodes(client, "hoaq"):
        if client.local and not client.has_permission("channel:override:mode"):
            return client.sendnumeric(Numeric.ERR_CHANOPRIVSNEEDED, channel.name)
        else:
            override = 1

    send_ts, ts_change, should_continue = process_channel_timestamp(client, channel, recv)
    if not should_continue:
        return

    # # https://gist.github.com/jlu5/5233ebe64d5c8c1f079ef8c8fcb759ff#55-mode---channel-mode-token-g
    # send_ts = 0
    # if str(recv[-1]).isdigit():
    #     timestamp = int(recv[-1])
    #     if client.server and timestamp > 0:
    #         if client != IRCD.me and not client.is_uline():
    #             if timestamp > channel.creationtime:
    #                 msg = (f"Dropping MODE from server {client.name} for channel {channel.name}: "
    #                        f"their timestamp={timestamp}, ours={channel.creationtime}")
    #                 IRCD.log(client, "warn", "mode", "MODE_TS_IGNORED", message=msg)
    #                 return
    #         if timestamp < channel.creationtime:
    #             logging.warning(f"Channel {channel.name} timestamp updated from {channel.creationtime} to {timestamp}")
    #             channel.creationtime = timestamp
    #             send_ts = timestamp

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

        """ Handle params """
        if mode in list(IRCD.get_list_modes_str()) + param_modes + param_modes_unset:
            if (mode in param_modes and action == '+'
                    or mode in list(IRCD.get_list_modes_str()) + param_modes_unset):
                if len(params) <= paramcount:
                    continue

            if action == '+' or cmode.unset_with_param:
                param = params[paramcount]
                param = IRCD.strip_format(param)
                paramcount += 1

        if mode in IRCD.get_list_modes_str():
            def do_list_mode(mask_param):
                nonlocal prevaction
                if returned_param := handle_mode_list(client, channel, action, mode, mask_param):
                    prevaction = add_to_buff(modebuf, parambuf, action, prevaction, mode, returned_param)

            if action == '-' and (target_client := IRCD.find_client(param)):
                for entry in list(channel.List[mode]):
                    if channel.check_match(target_client, mode, mask=entry.mask):
                        do_list_mode(entry.mask)
            else:
                do_list_mode(param)

            continue

        if client.user:
            allowed = cmode.is_ok(client, channel, action, mode, param, cmode.CHK_ACCESS) or not client.local
            if not allowed and client.has_permission("channel:override:mode"):
                allowed = override = 1

            match int(allowed):
                case 0:  # Not allowed.
                    if cmode.is_ok == Channelmode.allow_opers:
                        client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
                    elif cmode.level == 5:
                        client.sendnumeric(Numeric.ERR_CHANOWNPRIVNEEDED, channel.name)
                    else:
                        client.sendnumeric(Numeric.ERR_CHANOPRIVSNEEDED, channel.name)
                    continue
                case -1:  # Not allowed. Let module handle feedback.
                    continue

        if client.user and client.local and not client.has_permission("channel:override:mode"):
            for callback, result in Hook.call(Hook.PRE_LOCAL_CHANNEL_MODE, args=(client, channel, modebuf, parambuf, action, mode, param)):
                if result == Hook.DENY:
                    continue

        oldcmodes = channel.modes
        if mode not in param_modes + param_modes_unset:
            if action == '+' and mode not in channel.modes:
                channel.modes += mode
            elif action == '-' and mode in channel.modes:
                channel.modes = channel.modes.replace(mode, '')

        elif mode in param_modes:
            # These modes require param on set, but not on unset.
            # Such as limit, +l
            if action == '+':
                if result := cmode.is_ok(client, channel, action, mode, param, cmode.CHK_PARAM) or not client.local:
                    channel.add_param(mode, param)
                    if mode not in channel.modes:
                        channel.modes += mode
                    else:
                        # These modes are special as you can + them to change their parameter.
                        # But if the mode is already set, code below won't trigger the modebuf append, so we do it here.
                        prevaction = add_to_buff(modebuf, parambuf, action, prevaction, mode, param)

            elif action == '-':
                if mode in channel.modes:
                    channel.modes = channel.modes.replace(mode, '')
                    if channel.get_param(mode):
                        channel.del_param(mode)

        elif mode in param_modes_unset:
            if cmode.type == cmode.MEMBER:
                if do_channel_member_mode(client, channel, action, mode, param):
                    nick = IRCD.find_client(param).name
                    prevaction = add_to_buff(modebuf, parambuf, action, prevaction, mode, param=nick)
                continue

            if not cmode.is_ok(client, channel, action, mode, param, cmode.CHK_PARAM) and client.local:
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
        action = ''
        for mode in modebuf:
            if mode in "+-":
                action = mode
            elif action:
                hook = Hook.MODEBAR_ADD if action == '+' else Hook.MODEBAR_DEL
                IRCD.run_hook(hook, client, channel, mode)

        send_modelines(client, channel, modebuf, parambuf, send_ts)

        if override and client.user and client.local:
            modes_set = ''.join(modebuf)
            params_set = ' '.join(parambuf)
            mode_string = f"{modes_set}{' ' + params_set if parambuf else ''}"
            IRCD.send_oper_override(client, f"with MODE {channel.name} {mode_string}")

    elif ts_change:
        logging.warning(f"Updating remote server {client.name} with our correct timestamp")
        IRCD.send_to_one_server(client, mtags=[], data=f":{IRCD.me.name} MODE {channel.name} + {channel.creationtime}")
        return

    if unknown and client.user:
        client.sendnumeric(Numeric.ERR_UNKNOWNMODE, ''.join(unknown))


def cmd_mode(client, recv):
    target = recv[1]
    if target[0] in IRCD.CHANPREFIXES:
        if not IRCD.find_channel(target):
            return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, target)
        cmd_channelmode(client, recv)
    else:
        if not IRCD.find_client(target, user=1):
            return client.sendnumeric(Numeric.ERR_NOSUCHNICK, target)
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
