"""
/svsmode, /svs2mode and /svssno command (server)
"""

from handle.core import IRCD, Command, Flag, Hook
from handle.functions import logging


def cmd_svsmode(client, recv):
    if not (target := IRCD.find_user(recv[1])):
        return

    action = ''
    modes = ''
    oldumodes = target.user.modes
    for m in recv[2]:
        if m in '+-' and m != action:
            action = m
            modes += action
            continue

        if m != "d" and m not in IRCD.get_umodes_str():
            continue

        if m == "d":  # Set or remove account.
            if len(recv) > 3:
                account = recv[3]
                curr_account = target.user.account
                target.user.account = account if account != "0" else "*"
                if curr_account != account:
                    IRCD.run_hook(Hook.ACCOUNT_LOGIN, target)
                continue
            elif m not in IRCD.get_umodes_str():
                continue

        if action == '+':
            if m not in target.user.modes:
                target.user.modes += m
                modes += m

        elif action == '-':
            if m in target.user.modes:
                target.user.modes = target.user.modes.replace(m, '')
                modes += m

    if recv[0].lower() == "svs2mode" and target.local and target.user.modes != oldumodes and len(modes) > 1:
        data = f":{client.name} MODE {target.name} {modes}"
        target.send([], data)

    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def cmd_svssno(client, recv):
    if not (target := IRCD.find_user(recv[1])):
        return

    action = ''
    snomasks = ''
    for m in recv[2]:
        if m in '+-' and m != action:
            action = m
            snomasks += action
            continue
        if action == '+':
            if recv[0].lower() == 'svssno':
                target.snomasks += m
            snomasks += m

        elif action == '-':
            if recv[0].lower() == 'svssno':
                target.snomasks = target.snomasks.replace(m, '')
            snomasks += m

    cmd_mode = Command.find_command(client, "MODE")
    cmd_mode.do(client, "MODE", target.name, "+s", snomasks)

    data = ' '.join(recv)
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_svsmode, "SVSMODE", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_svsmode, "SVS2MODE", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_svssno, "SVSSNO", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_svssno, "SVS2SNO", 2, Flag.CMD_SERVER)
