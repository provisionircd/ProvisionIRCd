"""
/squit command (server)
"""

from handle.core import Numeric, IRCD, Command, Flag
from handle.logger import logging


def cmd_squit(client, recv):
    logging.debug(f"SQUIT from {client.name}: {recv}")
    reason = client.name if len(recv) < 3 else ' '.join(recv[2:]).removeprefix(':')

    if client.user and client.local and not client.has_permission("server:squit"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if not (server_matches := IRCD.find_server_match(recv[1])):
        if client.user:
            client.sendnumeric(Numeric.ERR_NOSUCHSERVER, recv[1])
        else:
            logging.error(f"SQUIT received from {client.name} for non-existent server: {recv[1]} (no matches found)")
        return

    if recv[1] == IRCD.me.name:
        return IRCD.server_notice(client, "Cannot use /SQUIT on ourself.")

    for squit_client in server_matches:
        if squit_client == IRCD.me:
            continue

        data = f":{client.id} {' '.join(recv)}"
        IRCD.send_to_servers(client, [], data)

        if squit_client.server.synced:
            msg = f"{client.fullrealhost} used SQUIT for {squit_client.name}: {reason}"
            IRCD.log(client, "info", "squit", "LINK_SQUIT", msg, sync=0)

        squit_client.exit(reason)


def init(module):
    Command.add(module, cmd_squit, "SQUIT", 1, Flag.CMD_OPER, Flag.CMD_SERVER)
