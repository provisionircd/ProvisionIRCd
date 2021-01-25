"""
/chghost command
"""

import ircd


@ircd.Modules.command
class Chgident(ircd.Command):
    """
    Changes the ident (username) part of a user.
    Syntax: CHGIDENT <target> <newident>
    """

    def __init__(self):
        self.command = 'chgident'
        self.req_modes = 'o'
        self.params = 2

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            source = client
            client = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], self.ircd.users))
            if not client:
                return
            client = client[0]
            recv = recv[1:]
        else:
            source = self.ircd

        target = list(filter(lambda u: u.nickname == recv[1], self.ircd.users))
        if not target:
            return client.sendraw(self.ERR.NOSUCHNICK, '{} :No such nick'.format(recv[1]))
        target = target[0]
        ident = str(recv[2][:12]).strip()
        valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
        for c in str(ident):
            if c.lower() not in valid:
                ident = ident.replace(c, '').rstrip()
        if ident == target.ident or not ident:
            return
        target.setinfo(ident, t='ident', source=source)
        self.ircd.snotice('s', '*** {} ({}@{}) used CHGIDENT to change the ident of {} to "{}"'.format(client.nickname, client.ident, client.hostname, target.nickname, target.ident))
