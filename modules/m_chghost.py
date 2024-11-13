"""
/chghost and /chgident command
"""

from handle.core import IRCD, Command, Capability, Numeric, Flag


def cmd_chghost(client, recv):
    """
    Changes a users' cloak host.
    Syntax: CHGHOST <user> <newhost>
    """

    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    host = str(recv[2][:64]).strip().removeprefix(':')
    host = ''.join(c for c in host if c.lower() in IRCD.HOSTCHARS)

    host = host.removeprefix('.').removesuffix('.').strip()
    if host == target.user.cloakhost or not host:
        return

    target.setinfo(host, change_type="host")
    if client.user:
        if target.local:
            IRCD.server_notice(target, f"Your cloakhost has now been changed to: {target.user.cloakhost}")
        data = f"*** {client.name} ({client.user.username}@{client.user.realhost}) used CHGHOST to change the host of {target.name} to \"{target.user.cloakhost}\""
        IRCD.log(client, "info", "chgcmds", "CHGHOST_COMMAND", data)

    data = f":{client.id} CHGHOST {target.id} :{target.user.cloakhost}"
    IRCD.send_to_servers(client, [], data)


def cmd_chgident(client, recv):
    """
    Changes the ident (username) part of a user.
    Syntax: CHGIDENT <target> <newident>
    """

    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    ident = recv[2][:12].strip().removeprefix(':')
    ident = ''.join(c for c in ident if c.lower() in IRCD.HOSTCHARS)

    ident = ident.removeprefix('.').removesuffix('.').strip()
    if ident == target.user.username or not ident:
        return

    target.setinfo(ident, change_type="ident")
    if client.user:
        if target.local:
            IRCD.server_notice(target, f"Your ident has now been changed to: {target.user.username}")
        data = f"*** {client.name} ({client.user.username}@{client.user.realhost}) used CHGIDENT to change the ident of {target.name} to \"{target.user.username}\""
        IRCD.log(client, "info", "chgcmds", "CHGIDENT_COMMAND", data, sync=0)

    data = f":{client.id} CHGIDENT {target.id} :{target.user.username}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_chghost, "CHGHOST", 2, Flag.CMD_OPER)
    Command.add(module, cmd_chgident, "CHGIDENT", 2, Flag.CMD_OPER)
    Capability.add("chghost")
