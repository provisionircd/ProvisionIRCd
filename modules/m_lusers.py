"""
/lusers command
"""

from handle.core import IRCD, Numeric, Command


def cmd_lusers(client, recv):
    def s(n):
        return 's' * (n != 1)

    servers = sum(c.server.synced for c in IRCD.get_clients(server=1)) + 1
    users = sum('i' not in c.user.modes for c in IRCD.get_clients(user=1))
    invisible = sum(1 for _ in IRCD.get_clients(user=1, usermodes='i'))
    opers = sum(not c.is_uline() and 'H' not in c.user.modes for c in IRCD.get_clients(user=1, usermodes='o'))
    unknown = sum(1 for _ in IRCD.get_clients(registered=0))
    my_servers = sum(1 for _ in IRCD.get_clients(local=1, server=1))
    luserclient_args = ("are" if users - 1 else "is", users, 's' * (users != 1), invisible, servers, 's' * (servers != 1))

    client.sendnumeric(Numeric.RPL_LUSERCLIENT, *luserclient_args)
    client.sendnumeric(Numeric.RPL_LUSEROP, opers, s(opers))
    if unknown:
        client.sendnumeric(Numeric.RPL_LUSERUNKNOWN, unknown, s(unknown))
    client.sendnumeric(Numeric.RPL_LUSERCHANNELS, IRCD.channel_count, s(IRCD.channel_count))
    client.sendnumeric(Numeric.RPL_LUSERME, IRCD.local_client_count, s(IRCD.local_client_count), my_servers, s(my_servers))
    client.sendnumeric(Numeric.RPL_LOCALUSERS, IRCD.local_user_count, s(IRCD.local_user_count), IRCD.maxusers)
    client.sendnumeric(Numeric.RPL_GLOBALUSERS, IRCD.global_user_count, s(IRCD.global_user_count), IRCD.maxgusers)


def init(module):
    Command.add(module, cmd_lusers, "LUSERS")
