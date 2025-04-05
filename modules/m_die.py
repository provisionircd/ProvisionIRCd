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

    if client.user:
        if recv[1] != IRCD.get_setting("diepass"):
            client.local.flood_penalty += 2500001
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    reason = (f"DIE command received by {client.name} ({client.user.username}@{client.user.realhost})"
              if client.user else "DIE command received from the command line.")

    IRCD.send_snomask(client, 's', f"*** {reason}")

    for server in IRCD.get_clients(local=1, server=1):
        server.send([], f"SQUIT {IRCD.me.name} :{reason}")

    IRCD.run_parallel_function(IRCD.shutdown, delay=0.1)


def init(module):
    Command.add(module, cmd_die, "DIE", 1, Flag.CMD_OPER)
