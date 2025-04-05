"""
/ison and /userhost command
"""

from handle.core import IRCD, Command, Numeric


def cmd_ison(client, recv):
    """
    Checks to see if a nickname is online.
    Example: /ISON Nick1 SomeOthernick
    """

    nicks = []
    for nick in recv[1:]:
        for u_client in [u_client for u_client in IRCD.get_clients(user=1)
                         if u_client.name.lower() == nick.lower() and u_client.name not in nicks]:
            nicks.append(u_client.name)
    client.sendnumeric(Numeric.RPL_ISON, ' '.join(nicks))


def cmd_userhost(client, recv):
    """
    Returns the cloaked userhost of the given user.
    Example: /USERHOST John
    """

    hosts = []
    for nick in recv[1:]:
        for u_client in [u_client for u_client in IRCD.get_clients(user=1) if
                         u_client.name.lower() == nick.lower() and u_client.name not in hosts]:
            h = (f"{u_client.name}*=+{u_client.user.username}@"
                 f"{u_client.user.host if 'o' not in u_client.user.modes else u_client.user.realhost}")
            if h not in hosts:
                hosts.append(h)
    client.sendnumeric(Numeric.RPL_USERHOST, ' '.join(hosts))


def init(module):
    Command.add(module, cmd_ison, "ISON", 1)
    Command.add(module, cmd_userhost, "USERHOST", 1)
