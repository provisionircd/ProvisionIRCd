"""
/away command
"""

import ircd
from handle.functions import checkSpamfilter

AWAYLEN = 307


@ircd.Modules.command
class Away(ircd.Command):
    def __init__(self):
        self.command = 'away'
        self.support = [('AWAYLEN', AWAYLEN)]

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            sourceServer = client
            client = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], self.ircd.users))[0]
            data = ' '.join(recv)
            recv = recv[1:]
        else:
            data = ':{} {} :{}'.format(client.uid, ''.join(recv[0]), ' '.join(recv[1:]))
            sourceServer = client.server

        if len(recv) < 2:
            if not client.away:
                return
            client.away = False
            client.sendraw(305, ':You are no longer marked as being away')
        else:
            away = ' '.join(recv[1:])[:AWAYLEN]

            if checkSpamfilter(client, self.ircd, client.nickname, 'away', away):
                return

            client.away = away
            if client.away.startswith(':'):
                client.away = client.away[1:]
            client.sendraw(306, ':You have been marked as being away')

        updated = []
        for user in self.ircd.users:
            for user in [user for user in self.ircd.users if 'away-notify' in user.caplist and user not in updated and user.socket]:
                common_chan = list(filter(lambda c: user in c.users and client in c.users, self.ircd.channels))
                if not common_chan:
                    continue
                user._send(':{} AWAY {}'.format(client.fullmask(), '{}'.format(':' + client.away if client.away else '')))
                updated.append(user)

        self.ircd.new_sync(self.ircd, sourceServer, data)
