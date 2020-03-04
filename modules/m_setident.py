"""
/setident command
"""

import ircd

class Setident(ircd.Command):
    def __init__(self):
        self.command = 'setident'
        self.param = 1
        self.req_modes = 'o'

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            source = self
            client = next((u for u in self.ircd.users if u.uid == recv[0][1:] or u.nickname == recv[0][1:]), None)
            if not client:
                return
            recv = recv[1:]
            ident = str(recv[1]).strip()
            client.setinfo(ident, t='ident', source=source)
            return
        else:
            source = self.ircd

        ident = str(recv[1][:64]).strip()
        valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
        for c in str(ident):
            if c.lower() not in valid:
                ident = ident.replace(c, '')
        if ident and ident != client.ident:
            client.setinfo(ident, t='ident', source=source)
            self.ircd.notice(client, '*** Your ident is now "{}"'.format(client.ident))
