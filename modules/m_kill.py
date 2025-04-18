"""
/kill command
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_kill(client, recv):
    """
    Forcefully disconnect a user from the server.
    Syntax: /KILL <user> <reason>
    """

    if not (target := IRCD.find_client(recv[1], user=1)):
        client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])
        return

    if client.local and (not target.local and not client.has_permission("kill:global")
                         or target.local and not client.has_permission("kill:local")):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if client.is_local_user() and IRCD.is_except_client("kill", target):
        return client.sendnumeric(Numeric.ERR_KILLDENY, target.name)

    if not client.has_permission("kill:oper"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    reason = ' '.join(recv[2:]).removeprefix(':')
    target.kill(reason, killed_by=client)


def init(module):
    Command.add(module, cmd_kill, "KILL", 2, Flag.CMD_OPER)
