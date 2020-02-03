"""
/chghost command
"""

import ircd

@ircd.Modules.command
class Chghost(ircd.Command):
    """
    Changes a users' cloak host.
    Syntax: CHGHOST <user> <newhost>
    """
    def __init__(self):
        self.command = 'chghost'
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
        host = str(recv[2][:64]).strip()
        valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
        for c in str(host):
            if c.lower() not in valid:
                host = host.replace(c, '')
        if host == target.cloakhost or not host:
            return
        target.setinfo(host, t='host', source=source)
        self.ircd.snotice('s', '*** {} ({}@{}) used CHGHOST to change the host of {} to "{}"'.format(client.nickname, client.ident, client.hostname, target.nickname, target.cloakhost))
