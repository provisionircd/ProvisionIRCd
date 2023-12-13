"""
/clones command
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_clones(client, recv):
    clones, foundclones = [], False
    for user_client in IRCD.global_users():
        if user_client.ip not in clones:
            clones.append(user_client.ip)
            logins = [c for c in IRCD.global_users() if c.registered and not c.ulined and 'S' not in c.user.modes and c.ip == user_client.ip]
            if len(logins) > 1:
                foundclones = 1
                nicks = []
                for clone_client in logins:
                    nicks.append(clone_client.name)
                client.sendnumeric(Numeric.RPL_CLONES, user_client.name, len(logins), ' '.join(nicks))

    if not foundclones:
        client.sendnumeric(Numeric.RPL_NOCLONES, "server" if not IRCD.global_servers() else "network")


def init(module):
    Command.add(module, cmd_clones, "CLONES", 0, Flag.CMD_OPER)
