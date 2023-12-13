"""
/restart command
"""

import os
import sys

from handle.core import IRCD, Command, Numeric, Flag
from threading import Thread
from time import sleep


def do_restart():
    IRCD.running = 0
    sleep(0.1)
    Thread(target=exit).start()
    python = sys.executable
    os.execl(python, python, *sys.argv)


def cmd_restart(client, recv):
    """
    RESTART <password>
    -
    Restarts the server.
    """
    if not client.has_permission("server:restart"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
    if recv[1] != IRCD.get_setting("restartpass"):
        client.local.flood_penalty += 2500001
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    reason = f'RESTART command received by {client.name} ({client.user.username}@{client.user.realhost})'
    msg = f"*** {reason}"
    IRCD.send_snomask(client, 's', msg)

    for server in IRCD.local_servers():
        server.send([], f"SQUIT {IRCD.me.name} :{reason}")

    for user in IRCD.local_users():
        user.exit("Server is restarting")

    Thread(target=do_restart).start()


def init(module):
    Command.add(module, cmd_restart, "RESTART", 1, Flag.CMD_OPER)
