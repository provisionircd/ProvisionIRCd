"""
/connect command
"""

from handle.logger import logging
from handle.handleLink import start_outgoing_link
from handle.core import IRCD, Command, Numeric, Flag


def connect_to(client, link, auto_connect=0):
    try:
        if "host" not in link.outgoing or "port" not in link.outgoing:
            return
        # If the host is local, and you are listening for servers on the port, do not connect to yourself.
        out_host, out_port = link.outgoing["host"], int(link.outgoing["port"])
        if out_host in ["127.0.0.1", "0.0.0.0", "localhost"] and \
                (out_port in [int(listen.port) for listen in IRCD.configuration.listen]):
            if client and client.user:
                IRCD.server_notice(client, f"Unable to process outgoing link {out_host}:{out_port} because destination is localhost.")
            return
        is_tls = 0
        if "tls" in link.outgoing_options or "ssl" in link.outgoing_options:
            is_tls = 1

        if client.user:
            msg = f"*** {client.name} ({client.user.username}@{client.fullrealhost}) has opened a{' secure' if is_tls else 'n insecure'} link channel to {link.name}..."
            IRCD.log(client, "info", "link", "LINK_CONNECTING", msg)
        if not IRCD.find_server(link.name) and not IRCD.current_link_sync:
            IRCD.run_parallel_function(target=start_outgoing_link, args=(link, is_tls, auto_connect))

    except Exception as ex:
        logging.exception(ex)


def cmd_connect(client, recv):
    """
    Used by IRC Operators to request a link with a pre-configured server.
    Syntax: CONNECT <servername>

    Note that <servername> should match a server in your configuration file.
    """
    if not client.has_permission("server:connect"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
    if 'HTTP/' in recv:
        client.exit('Illegal command')
        return
    if IRCD.current_link_sync:
        client.local.flood_penalty += 100_000
        return IRCD.server_notice(client, f"A link sync is already in process, try again in a few seconds.")
    name = recv[1].strip()
    if name.lower() == IRCD.me.name.lower():
        return IRCD.server_notice(client, "*** Cannot link to own local server.")

    if not (link := next((link for link in IRCD.configuration.links if link.name.lower() == name.lower()), 0)):
        return IRCD.server_notice(client, f"*** Server {name} is not configured for linking.")

    server_client = IRCD.find_server(name)

    if server_client:
        if not server_client.server.synced:
            return IRCD.server_notice(client, f"*** Link to {name} is currently being processed.")

        if server_client.server.synced:
            return IRCD.server_notice(client, f"*** Already linked to {name}.")

    if not link.outgoing:
        return IRCD.server_notice(client, f"*** Server {name} is not configured as an outgoing link.")

    client.local.flood_penalty += 100_000
    connect_to(client, link)


def init(module):
    Command.add(module, cmd_connect, "CONNECT", 1, Flag.CMD_OPER)
