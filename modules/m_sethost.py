"""
/sethost and /setident command
"""

from handle.core import IRCD, Command, Capability, Flag


def cmd_sethost(client, recv):
    """
    Changes your own hostmask.
    Syntax:     SETHOST <host>
    """

    host = IRCD.clean_string(string=recv[1], charset=IRCD.HOSTCHARS, maxlen=64)
    host = host.removeprefix(':')

    if host and host != client.user.host:
        client.add_user_modes("xt")
        client.set_host(host=host)
        if client.local:
            IRCD.server_notice(client, f"*** Your host is now '{client.user.host}'")

        IRCD.send_to_servers(client, [], data=f":{client.id} SETHOST {client.user.host}")


def cmd_setident(client, recv):
    """
    Changes your own username (ident).
    Syntax:     SETIDENT <ident>
    """

    ident = IRCD.clean_string(string=recv[1], charset=IRCD.HOSTCHARS, maxlen=12)
    ident = ident.removeprefix(':')

    if ident == client.user.username or not ident:
        return

    client.user.username = ident

    if client.local:
        IRCD.server_notice(client, f"*** Your ident is now '{client.user.username}'")

    IRCD.send_to_servers(client, [], data=f":{client.id} SETIDENT {client.user.username}")


def init(module):
    Command.add(module, cmd_sethost, "SETHOST", 1, Flag.CMD_OPER)
    Command.add(module, cmd_setident, "SETIDENT", 1, Flag.CMD_OPER)
    Capability.add("chghost")
