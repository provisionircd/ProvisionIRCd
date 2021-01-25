"""
/sanick command
"""

import ircd


@ircd.Modules.command
class Sanick(ircd.Command):
    """
    Forcefully change a users nickname.
    Syntax: /SANICK <user> <newnick>
    """

    def __init__(self):
        self.command = 'sanick'
        self.params = 2
        self.req_modes = 'o'
        self.req_flags = ('localsacmds|globalsacmds')

    def execute(self, client, recv):
        target = list(filter(lambda c: c.nickname.lower() == recv[1].lower(), self.ircd.users))
        if not target:
            return client.sendraw(self.ERR.NOSUCHNICK, '{} :No such nick'.format(recv[1]))

        if target[0].server != self.ircd:
            return self.ircd.notice(client, "You cannot /sanick remote users")
            # return client.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')

        if target[0].nickname == recv[2]:
            return

        nick = list(filter(lambda u: u.nickname == recv[2], self.ircd.users))
        if nick:
            return self.ircd.notice(client, '*** Nickname {} is already in use'.format(nick[0].nickname))

        if recv[2][0].isdigit():
            return self.ircd.handle('NOTICE', '{} :*** Nicknames may not start with a number'.format(client.uid))

        client.flood_penalty += 100000

        p = {'sanick': client}
        target[0].handle('nick', recv[2], params=p)
