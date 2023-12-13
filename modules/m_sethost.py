"""
/sethost and /setident command
"""

from handle.core import Command, Capability, Flag, IRCD
from handle.logger import logging


def cmd_sethost(client, recv):
    logging.debug(f"SETHOST from {client.name}: {recv}")
    host = str(recv[1][:64]).strip().removeprefix(':')
    for c in str(host):
        if c.lower() not in IRCD.HOSTCHARS:
            host = host.replace(c, '')
    host = host.removeprefix('.').removesuffix('.').strip()
    if host and host != client.user.cloakhost:
        client.setinfo(host, t="host")

    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def cmd_setident(client, recv):
    ident = str(recv[1][:64]).strip().removeprefix(':')
    for c in str(ident):
        if c.lower() not in IRCD.HOSTCHARS:
            ident = ident.replace(c, '')
    ident = ident.removeprefix('.').removesuffix('.').strip()
    if ident and ident != client.user.username:
        client.setinfo(ident, t="ident")
        if client.local:
            IRCD.server_notice(client, f"*** Your ident is now '{client.user.username}'")
    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_sethost, "SETHOST", 1, Flag.CMD_OPER)
    Command.add(module, cmd_setident, "SETIDENT", 1, Flag.CMD_OPER)
    Capability.add("chghost")
