"""
/restart command
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_restart(client, recv):
    """
    RESTART <password>
    -
    Restarts the server.
    """

    if not client.has_permission("server:restart"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if client.user:
        if recv[1] != IRCD.get_setting("restartpass"):
            client.local.flood_penalty += 2500001
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    reason = (f"RESTART command received by {client.name} ({client.user.username}@{client.user.realhost})"
              if client.user else "RESTART command received from the command line.")

    IRCD.send_snomask(client, 's', f"*** {reason}")

    for server in IRCD.get_clients(local=1, server=1):
        server.send([], f"SQUIT {IRCD.me.name} :{reason}")

    IRCD.run_parallel_function(IRCD.restart, delay=0.1)


def init(module):
    Command.add(module, cmd_restart, "RESTART", 1, Flag.CMD_OPER)
