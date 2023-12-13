"""
/lusers command
"""

from handle.core import IRCD, Numeric, Command
from handle.logger import logging


def cmd_lusers(client, recv):
    servers = len([c for c in IRCD.global_servers() if c.server.synced]) + 1
    invisible = len([c for c in IRCD.global_users() if 'i' in c.user.modes])
    opers = len([c for c in IRCD.global_users() if 'o' in c.user.modes and not c.ulined and 'H' not in c.user.modes])
    unknown = len(IRCD.unregistered_clients())
    my_servers = len(list(IRCD.local_servers()))

    luserclient_args = 'are' if IRCD.global_user_count != 1 else 'is', IRCD.global_user_count, 's' \
        if IRCD.global_user_count != 1 else '', invisible, servers, 's' if servers != 1 else ''

    client.sendnumeric(Numeric.RPL_LUSERCLIENT, *luserclient_args)
    client.sendnumeric(Numeric.RPL_LUSEROP, opers, 's' if opers != 1 else '')
    if unknown > 0:
        client.sendnumeric(Numeric.RPL_LUSERUNKNOWN, unknown, 's' if unknown != 1 else '')
    client.sendnumeric(Numeric.RPL_LUSERCHANNELS, IRCD.channel_count, 's' if IRCD.channel_count != 1 else '')
    client.sendnumeric(Numeric.RPL_LUSERME, IRCD.local_client_count, 's' if IRCD.local_client_count != 1 else '', my_servers, 's' if my_servers != 1 else '')
    client.sendnumeric(Numeric.RPL_LOCALUSERS, IRCD.local_user_count, 's' if IRCD.local_user_count != 1 else '', IRCD.maxusers)
    client.sendnumeric(Numeric.RPL_GLOBALUSERS, IRCD.global_user_count, 's' if IRCD.global_user_count != 1 else '', IRCD.maxgusers)


def init(module):
    Command.add(module, cmd_lusers, "LUSERS")
