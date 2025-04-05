"""
/pass command (server)
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_pass(client, recv):
    if not client.registered:
        client.local.authpass = recv[1].removeprefix(':')
    else:
        return client.sendnumeric(Numeric.ERR_ALREADYREGISTRED)

    if client.server:
        if not IRCD.configuration.links:
            return client.exit("Target has no links configured")


def init(module):
    Command.add(module, cmd_pass, "PASS", 1, Flag.CMD_UNKNOWN)
