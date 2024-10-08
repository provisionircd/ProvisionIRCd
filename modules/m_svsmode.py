"""
/svsmode, /svs2mode and /svssno command (server)
"""

from handle.core import IRCD, Command, Flag, Hook, Numeric


def cmd_svsmode(client, recv):
    """
    SVSMODE is used to change a user's modes.
    Using SVS2MODE will display the change to the target user.
    -
    Server-only command.
    """

    if not (target := IRCD.find_user(recv[1])):
        return

    action = ''
    modes = ''
    oldumodes = target.user.modes
    for m in recv[2]:
        if m in "+-" and m != action:
            action = m
            modes += action
            continue

        if m != 'd' and m not in IRCD.get_umodes_str():
            continue

        if m == 'd':  # Set or remove account.
            if len(recv) > 3:
                account = recv[3]
                curr_account = target.user.account
                target.user.account = account if account != '0' else '*'
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
    """
    SVSSNO is used to change a user's snomasks.
    Using SVS2SNO will display the change to the target user.
    -
    Server-only command.
    """

    if not (target := IRCD.find_user(recv[1])):
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
    Command.add(module, cmd_svsmode, "SVSMODE", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_svsmode, "SVS2MODE", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_svssno, "SVSSNO", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_svssno, "SVS2SNO", 2, Flag.CMD_SERVER)
