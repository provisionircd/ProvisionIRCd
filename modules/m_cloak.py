"""
/cloak command
"""

from handle.core import Command, IRCD, Flag


def cmd_cloak(client, recv):
    IRCD.server_notice(client, f'* Cloaked version is: {IRCD.get_cloak(client, host=recv[1])}')


def init(module):
    Command.add(module, cmd_cloak, "CLOAK", 1, Flag.CMD_OPER)
