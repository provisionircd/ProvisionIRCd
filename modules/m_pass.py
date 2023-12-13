"""
/pass command (server)
"""

from handle.core import Numeric, IRCD, Command, Flag
from handle.logger import logging


def cmd_pass(client, recv):
    if not client.registered:
        client.local.authpass = recv[1].removeprefix(':')
        logging.debug(f"Password set for local client {client.name}: {client.local.authpass}")
    else:
        return client.sendnumeric(Numeric.ERR_ALREADYREGISTRED)

    if client.server:
        if not IRCD.configuration.links:
            return client.exit("Target has no links configured")


def init(module):
    Command.add(module, cmd_pass, "PASS", 2, Flag.CMD_UNKNOWN)
