"""
/error command (server)
"""

from handle.core import IRCD, Command, Flag


def cmd_error(client, recv):
    if (link := IRCD.get_link(client.name)) and link.auto_connect and not client.server.authed:
        """ Do not spam ERROR messages on outgoing autoconnect fails. """
        return
    msg = ' '.join(recv[1:]).removeprefix(':')
    IRCD.log(IRCD.me, "error", "error", "ERROR_LINK", msg)


def init(module):
    Command.add(module, cmd_error, "ERROR", 1, Flag.CMD_SERVER)
