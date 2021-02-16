"""
/svsnick command (server)
"""

import ircd


class Svsnick(ircd.Command):
    def __init__(self):
        self.command = 'svsnick'
        self.req_class = 'Server'

    def execute(self, client, recv):
        S = recv[0][1:]
        source = [s for s in self.ircd.servers + [ircd] if s.sid == S or s.hostname == S] + [u for u in ircd.users if u.uid == S or u.nickname == S]
        if not source:
            return
        source = source[0]
        target = list(filter(lambda u: u.uid == recv[2] or u.nickname == recv[2], ircd.users))
        if not target:
            return
        p = {'sanick': source}
        target[0].handle('nick', recv[3], params=p)
