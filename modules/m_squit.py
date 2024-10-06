"""
/squit command (server)
"""

from handle.core import Numeric, IRCD, Command, Flag
from handle.logger import logging


def cmd_squit(client, recv):
    logging.warning(f"SQUIT from {client.name}: {recv}")
    reason = client.name if len(recv) < 3 else ' '.join(recv[2:]).removeprefix(':')

    if client.user and client.local and not client.has_permission("server:squit"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if not (server_matches := IRCD.find_server_match(recv[1])):
        if client.user:
            client.sendnumeric(Numeric.ERR_NOSUCHSERVER, recv[1])
        return

    if recv[1] == IRCD.me.name:
        return IRCD.server_notice(client, "Cannot use /SQUIT on ourself.")

    for squit_server in server_matches:
        if squit_server == IRCD.me:
            continue

        data = f":{client.id} {' '.join(recv)}"
        IRCD.send_to_servers(client, [], data)

        msg = f"{client.fullrealhost} used SQUIT command for {squit_server.name}: {reason}"
        IRCD.log(client, "info", "squit", "LINK_SQUIT", msg, sync=0)

        squit_server.exit(reason)


def init(module):
    Command.add(module, cmd_squit, "SQUIT", 1, Flag.CMD_OPER, Flag.CMD_SERVER)
