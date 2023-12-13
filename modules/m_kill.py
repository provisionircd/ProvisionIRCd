"""
/kill command
"""

from handle.core import IRCD, Command, Numeric, Flag

from handle.functions import is_match
from handle.logger import logging


def cmd_kill(client, recv):
    """
    Forcefully disconnect a user from the server.
    Syntax: /KILL <user> <reason>
    """

    target = IRCD.find_user(recv[1])
    if not target:
        if client.user:
            client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])
        return

    if client.local and (not target.local and not client.has_permission("kill:global")
                         or target.local and not client.has_permission("kill:local")):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if client.user and IRCD.is_except_client("kill", target):
        IRCD.server_notice(client, f"*** User {target.name} matches a kill-except and cannot be killed")
        client.sendnumeric(Numeric.ERR_KILLDENY, target.name)
        return

    if "o" in target.user.modes and not client.has_permission("kill:oper") and client.local:
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    reason = ' '.join(recv[2:]).removeprefix(":")
    target.kill(reason, killed_by=client)


def init(module):
    Command.add(module, cmd_kill, "KILL", 2, Flag.CMD_OPER)
