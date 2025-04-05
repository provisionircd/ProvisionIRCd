"""
/squit command (server)
"""

from handle.core import IRCD, Command, Numeric, Flag
from handle.logger import logging


@logging.client_context
def cmd_squit(client, recv):
    logging.debug(recv)
    target_name = recv[1]
    reason = client.name if len(recv) < 3 else ' '.join(recv[2:]).removeprefix(':')

    if client.user and client.local and not client.has_permission("server:squit"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if target_name.lower() == IRCD.me.name.lower():
        return IRCD.server_notice(client, "Cannot use /SQUIT on ourself.")

    if not (server_matches := IRCD.find_server_match(target_name)):
        if client.user:
            client.sendnumeric(Numeric.ERR_NOSUCHSERVER, target_name)
        return

    IRCD.send_to_servers(client, [], f":{client.id} SQUIT {target_name} :{reason}")

    for squit_client in server_matches:
        if squit_client == IRCD.me:
            continue

        if squit_client.server.authed:
            msg = f"{client.fullrealhost} used SQUIT for {squit_client.name}: {reason}"
            IRCD.log(client, "info", "squit", "LINK_SQUIT", msg, sync=0)

        squit_client.exit(reason)


def init(module):
    Command.add(module, cmd_squit, "SQUIT", 1, Flag.CMD_OPER, Flag.CMD_SERVER)
