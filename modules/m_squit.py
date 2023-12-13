"""
/squit command (server)
"""

from handle.core import Numeric, IRCD, Command, Flag
from handle.logger import logging


def cmd_squit(client, recv):
    if len(recv) < 3:
        reason = client.name
    else:
        reason = ' '.join(recv[2:]).removeprefix(':')
    logging.warning(f"SQUIT from {client.name}: {recv}")
    if client.user and client.local and not client.has_permission("server:squit"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    # reason = f'[{client.name}] {" ".join(recv[2:])}'
    name = recv[1]
    if not (squit_server := IRCD.find_server(name)):
        if client.user:
            client.sendnumeric(Numeric.ERR_NOSUCHSERVER, name)
        return
    if squit_server == IRCD.me:
        return logging.error(f"We cannot SQUIT ourself: {recv}")

    # data = f":{client.id} {' '.join(recv)}"
    # IRCD.send_to_servers(client, [], data)

    if client.user:
        msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) used SQUIT command for {squit_server.name}: {reason}"
        IRCD.log(client, "info", "link", "LINK_SQUIT", msg)
        # IRCD.send_snomask(client, 's', msg)

    squit_server.exit(reason)
    return


def init(module):
    Command.add(module, cmd_squit, "SQUIT", 1, Flag.CMD_OPER, Flag.CMD_SERVER)
