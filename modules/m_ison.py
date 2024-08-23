"""
/ison and /userhost command
"""

from handle.core import Numeric, Command, IRCD


def cmd_ison(client, recv):
    """
    Checks to see if a nickname is online.
    Example: /ISON Nick1 SomeOthernick
    """

    nicks = []
    for nick in recv[1:]:
        for u_client in [u_client for u_client in IRCD.global_users() if u_client.name.lower() == nick.lower() and u_client.name not in nicks]:
            nicks.append(u_client.name)
    client.sendnumeric(Numeric.RPL_ISON, ' '.join(nicks))


def cmd_userhost(client, recv):
    """
    Returns the cloaked userhost of the given user.
    Example: /USERHOST John
    """

    hosts = []
    for nick in recv[1:]:
        for u_client in [u_client for u_client in IRCD.global_users() if u_client.name.lower() == nick.lower() and u_client.name not in hosts]:
            h = f"{u_client.name}*=+{u_client.user.username}@{u_client.user.cloakhost if 'o' not in u_client.user.modes else u_client.user.realhost}"
            if h not in hosts:
                hosts.append(h)
    client.sendnumeric(Numeric.RPL_USERHOST, ' '.join(hosts))


def init(module):
    Command.add(module, cmd_ison, "ISON", 1)
    Command.add(module, cmd_userhost, "USERHOST", 1)
