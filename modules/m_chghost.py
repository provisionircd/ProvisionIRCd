"""
/chghost and /chgident command
"""

from handle.core import IRCD, Command, Capability, Numeric, Flag
from handle.logger import logging


def cmd_chghost(client, recv):
    """
    Changes a users' cloak host.
    Syntax: CHGHOST <user> <newhost>
    """
    logging.debug(f"CHGHOST from {client.name}: {recv}")
    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])
    host = str(recv[2][:64]).strip()
    for c in str(host):
        if c.lower() not in IRCD.HOSTCHARS:
            host = host.replace(c, '')
    host = host.removeprefix('.').removesuffix('.').strip()
    if host == target.user.cloakhost or not host:
        return
    target.setinfo(host, t="host")
    if client.user:
        IRCD.send_snomask(client, 's',
                          f'*** {client.name} ({client.user.username}@{client.user.realhost}) '
                          f'used CHGHOST to change the host of {target.name} to "{target.user.cloakhost}"')
    data = f":{client.id} CHGHOST {target.id} :{target.user.cloakhost}"
    logging.debug(f"Syncing CHGHOST to servers: {data}")
    IRCD.send_to_servers(client, [], data)


def cmd_chgident(client, recv):
    """
    Changes the ident (username) part of a user.
    Syntax: CHGIDENT <target> <newident>
    """
    logging.debug(f"CHGIDENT from {client.name}: {recv}")
    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])
    ident = str(recv[2][:12]).strip().removeprefix(':')
    for c in str(ident):
        if c.lower() not in IRCD.HOSTCHARS:
            ident = ident.replace(c, '')
    ident = ident.removeprefix('.').removesuffix('.').strip()
    if ident == target.user.username or not ident:
        return
    target.setinfo(ident, t="ident")
    if client.user:
        IRCD.send_snomask(client, 's',
                          f'*** {client.name} ({client.user.username}@{client.user.realhost}) '
                          f'used CHGIDENT to change the ident of {target.name} to "{target.user.username}"')
    data = f":{client.id} CHGIDENT {target.id} :{target.user.username}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_chghost, "CHGHOST", 2, Flag.CMD_OPER)
    Command.add(module, cmd_chgident, "CHGIDENT", 2, Flag.CMD_OPER)
    Capability.add("chghost")
