"""
/quit command
"""

from handle.core import Flag, IRCD, Command
from handle.logger import logging


def cmd_quit(client, recv):
    if not client.user:
        return
    if len(recv) > 1:
        reason = ' '.join(recv[1:][:128]).removeprefix(":")
    else:
        reason = client.name

    if not (quitprefix := IRCD.get_setting("quitprefix")):
        quitprefix = "Quit"

    if static_quit := IRCD.get_setting("static-quit"):
        reason = static_quit[:128]

    if not reason.strip():
        reason = client.name

    reason = f'{quitprefix + ": " if client.local else ""}{reason}'
    client.exit(reason)


def init(module):
    Command.add(module, cmd_quit, "QUIT", 0, Flag.CMD_USER)
