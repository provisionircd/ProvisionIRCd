"""
/clones command
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_clones(client, recv):
    """
    View clones on the network.
    """

    clones = set()
    foundclones = 0

    for user_client in IRCD.get_clients(user=1):
        if user_client.ip not in clones:
            clones.add(user_client.ip)
            logins = [
                c.name for c in IRCD.get_clients(user=1)
                if c.registered and not c.is_uline() and 'S' not in c.user.modes and c.ip == user_client.ip
            ]
            if len(logins) > 1:
                foundclones = 1
                client.sendnumeric(Numeric.RPL_CLONES, user_client.name, len(logins), user_client.ip, ' '.join(logins))

    if not foundclones:
        client.sendnumeric(Numeric.RPL_NOCLONES, "server" if not any(IRCD.get_clients(server=1)) else "network")


def init(module):
    Command.add(module, cmd_clones, "CLONES", 0, Flag.CMD_OPER)
