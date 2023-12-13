"""
/error command (server)
"""

from handle.core import IRCD, Command, Flag


def cmd_error(client, recv):
    msg = ' '.join(recv[1:]).removeprefix(":")
    IRCD.log(IRCD.me, "error", "error", "ERROR_LINK", msg)
    # IRCD.send_snomask(IRCD.me, 's', f"*** Error: {msg}")


def init(module):
    Command.add(module, cmd_error, "ERROR", 2, Flag.CMD_SERVER)
