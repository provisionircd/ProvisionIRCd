"""
/svsmode, /svs2mode and /svssno command (server)
"""

from handle.core import IRCD, Command, Flag, Hook, Numeric


def cmd_svsmode(client, recv):
    """
    SVSMODE is used to change a user's or channel's modes.
    Using SVS2MODE will display the change to the target user.
    -
    Server-only command.
    """

    if recv[1][0] not in IRCD.CHANPREFIXES:
        if not (target := IRCD.find_client(recv[1], user=1)):
            return

        action = ''
        modebuf = []
        param = ''
        oldmodes = target.user.modes

        if len(recv) > 3:
            param = IRCD.strip_format(recv[3])

        for m in recv[2]:
            if m in "+-" and m != action:
                action = m
                modebuf.append(action)
                continue

            if m != 'd' and m not in IRCD.get_umodes_str():
                continue

            if m == 'd':  # Set or remove account.
                if len(recv) > 3:
                    account = recv[3]
                    curr_account = target.user.account
                    target.user.account = account if account != '0' else '*'
                    if curr_account != account:
                        IRCD.run_hook(Hook.ACCOUNT_LOGIN, target, curr_account)
                continue

            if action == '+' and m not in target.user.modes:
                target.user.modes += m
                modebuf.append(m)

            elif action == '-' and m in target.user.modes:
                target.user.modes = target.user.modes.replace(m, '')
                modebuf.append(m)

        action = ''
        for mode in modebuf:
            if mode in "+-":
                action = mode
            elif action:
                hook = Hook.UMODE_SET if action == '+' else Hook.UMODE_UNSET
                IRCD.run_hook(hook, client, target, modebuf, mode)

        modes = ''.join(modebuf)
        if recv[0].lower() == "svs2mode" and target.local and target.user.modes != oldmodes and len(modes) > 1:
            target.send([], f":{client.name} MODE {target.name} {modes}")

        IRCD.run_hook(Hook.UMODE_CHANGE, client, target, oldmodes, target.user.modes)

    else:
        if not (channel := IRCD.find_channel(recv[1])):
            return

        action = ''
        paramcount = 0
        params = recv[3:]
        modes_out, params_out = '', []

        for mode in recv[2]:
            if mode in "+-":
                action = mode
                continue

            if mode in IRCD.get_list_modes_str():
                target_client = None
                if paramcount < len(params):
                    param = params[paramcount]
                    paramcount += 1
                    target_client = IRCD.find_client(param, user=1)

                if not target_client:
                    continue

                for entry in channel.List[mode]:
                    if not target_client or channel.check_match(target_client, mode, mask=entry.mask):
                        modes_out += mode
                        params_out.append(entry.mask)

            elif mode in IRCD.get_member_modes_str() and not params:
                cmode = IRCD.get_channelmode_by_flag(mode)
                for c in [c for c in channel.clients(prefix=cmode.prefix) if not c.is_uline()]:
                    modes_out += mode
                    params_out.append(c.name)

        if modes_out:
            Command.do(client, "MODE", channel.name, f"-{modes_out}", *params_out)

    IRCD.send_to_servers(client, [], f":{client.id} {' '.join(recv)}")


def cmd_svssno(client, recv):
    """
    SVSSNO is used to change a user's snomasks.
    Using SVS2SNO will display the change to the target user.
    -
    Server-only command.
    """

    if not (target := IRCD.find_client(recv[1], user=1)):
        return

    action = ''
    current_snomask = target.user.snomask

    for m in recv[2]:
        if m in "+-" and m != action:
            action = m
            continue

        if not IRCD.get_snomask(m):
            continue

        if action == '+' and m not in target.user.snomask:
            target.user.snomask += m

        elif action == '-' and m in target.user.snomask:
            target.user.snomask = target.user.snomask.replace(m, '')

    if not recv[2].lstrip('-'):
        target.user.snomask = ''

    if recv[0].lower() == "svs2sno":
        if current_snomask != target.user.snomask and target.local:
            target.sendnumeric(Numeric.RPL_SNOMASK, target.user.snomask)

    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_svsmode, "SVSMODE", 2, Flag.CMD_USER)
    Command.add(module, cmd_svsmode, "SVS2MODE", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_svssno, "SVSSNO", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_svssno, "SVS2SNO", 2, Flag.CMD_SERVER)
