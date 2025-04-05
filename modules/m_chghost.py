"""
/chghost and /chgident command
"""

from handle.core import IRCD, Command, Capability, Numeric, Flag
from handle.logger import logging


def cmd_chghost(client, recv):
    """
    Changes a users' host.
    Syntax: CHGHOST <user> <newhost>
    """

    permission_parent = "chgcmds:chghost"

    if not client.has_permission(f"{permission_parent}:local") and not client.has_permission(f"{permission_parent}:global"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if not (target := IRCD.find_client(recv[1], user=1)):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    if client.local:
        permission_check = f"{permission_parent}:global" if not target.local else f"{permission_parent}:local"
        if not client.has_permission(permission_check) and not client.has_permission(f"{permission_parent}:global"):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    host = IRCD.clean_string(string=recv[2], charset=IRCD.HOSTCHARS, maxlen=64)
    host = host.removeprefix(':')
    if host == target.user.host or not host:
        return

    target.add_user_modes("xt")
    target.set_host(host=host)

    if client.user:
        if target.local:
            IRCD.server_notice(target, f"Your hostname has now been changed to: {target.user.host}")
        data = (f"*** {client.name} ({client.user.username}@{client.user.realhost}) "
                f"used CHGHOST to change the host of {target.name} to \"{target.user.host}\"")
        IRCD.log(client, "info", "chgcmds", "CHGHOST_COMMAND", data)

    IRCD.send_to_servers(client, [], f":{client.id} CHGHOST {target.id} :{target.user.host}")


def cmd_chgident(client, recv):
    """
    Changes the ident (username) part of a user.
    Syntax: CHGIDENT <target> <newident>
    """

    permission_parent = "chgcmds:chgident"

    if not client.has_permission(f"{permission_parent}:local") and not client.has_permission(f"{permission_parent}:global"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if not (target := IRCD.find_client(recv[1], user=1)):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    if client.local:
        permission_check = f"{permission_parent}:global" if not target.local else f"{permission_parent}:local"
        if not client.has_permission(permission_check) and not client.has_permission(f"{permission_parent}:global"):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    ident = IRCD.clean_string(string=recv[2], charset=IRCD.HOSTCHARS, maxlen=12)
    ident = ident.removeprefix(':')

    if ident == target.user.username or not ident:
        return

    target.user.username = ident

    if client.user:
        if target.local:
            IRCD.server_notice(target, f"Your ident has now been changed to: {target.user.username}")
        data = (f"*** {client.name} ({client.user.username}@{client.user.realhost}) "
                f"used CHGIDENT to change the ident of {target.name} to \"{target.user.username}\"")
        IRCD.log(client, "info", "chgcmds", "CHGIDENT_COMMAND", data, sync=0)

    IRCD.send_to_servers(client, [], f":{client.id} CHGIDENT {target.id} :{target.user.username}")


def init(module):
    Command.add(module, cmd_chghost, "CHGHOST", 2, Flag.CMD_OPER)
    Command.add(module, cmd_chgident, "CHGIDENT", 2, Flag.CMD_OPER)
    Capability.add("chghost")
