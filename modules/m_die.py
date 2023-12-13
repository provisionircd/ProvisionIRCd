"""
/die command
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_die(client, recv):
    """
    DIE <password>
    -
    Shuts down the server.
    """
    if not client.has_permission("server:die"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
    if recv[1] != IRCD.get_setting("diepass"):
        client.local.flood_penalty += 2500001
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    reason = f'DIE command received by {client.name} ({client.user.username}@{client.user.realhost})'
    msg = f"*** {reason}"
    IRCD.send_snomask(client, 's', msg)

    for server in IRCD.local_servers():
        server.send([], f"SQUIT {IRCD.me.name} :{reason}")

    for user in IRCD.local_users():
        user.exit("Server is shutting down")

    IRCD.running = 0
    exit()


def init(module):
    Command.add(module, cmd_die, "DIE", 1, Flag.CMD_OPER)
