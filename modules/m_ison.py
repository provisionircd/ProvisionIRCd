"""
/ison and /userhost command
"""

import ircd


@ircd.Modules.command
class Ison(ircd.Command):
    """
    Checks to see if a nickname is online.
    Example: /ISON Nick1 SomeOthernick
    """

    def __init__(self):
        self.command = 'ison'
        self.params = 1

    def execute(self, client, recv):
        nicks = []
        for nick in recv[1:]:
            users = filter(lambda u: u.nickname.lower() == nick.lower() and u.registered, self.ircd.users)
            for user in [user for user in users if user.nickname not in nicks]:
                nicks.append(user.nickname)
        client.sendraw(self.RPL.ISON, ':{}'.format(' '.join(nicks)))


@ircd.Modules.command
class Userhost(ircd.Command):
    """
    Returns the cloaked userhost of the given user.
    Example: /USERHOST John
    """

    def __init__(self):
        self.command = 'userhost'
        self.params = 1

    def execute(self, client, recv):
        hosts = []
        for nick in recv[1:]:
            users = filter(lambda u: u.nickname.lower() == nick.lower() and u.registered, self.ircd.users)
            for user in users:
                h = '{}*=+{}@{}'.format(user.nickname, user.ident, user.cloakhost if 'o' not in self.modes else user.hostname)
                if h not in hosts:
                    hosts.append(h)
        client.sendraw(self.RPL.USERHOST, ':{}'.format(' '.join(hosts)))
