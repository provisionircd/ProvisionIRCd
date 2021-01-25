"""
/svsjoin and /svspart command (server)
"""

import ircd


@ircd.Modules.command
class Svsjoin(ircd.Command):
    def __init__(self):
        self.params = 2
        self.req_class = 'Server'
        self.command = 'svsjoin'

    def execute(self, client, recv):
        S = recv[0][1:]
        source = next([s for s in self.ircd.servers + [self.ircd] if s.sid == S or s.hostname == S] + [u for u in self.ircd.users if u.uid == S or u.nickname == S], None)
        if not source:
            return
        target = next((u for u in self.ircd.users if u.nickname == recv[2] or u.uid == recv[2]), None)
        if not target:
            return
        p = {'override': True}
        target.handle('join', recv[3], params=p)


@ircd.Modules.command
class Svspart(ircd.Command):
    def __init__(self):
        self.params = 2
        self.req_class = 'Server'
        self.command = 'svspart'

    def execute(self, client, recv):
        S = recv[0][1:]
        source = next([s for s in self.ircd.servers + [self.ircd] if s.sid == S or s.hostname == S] + [u for u in self.ircd.users if u.uid == S or u.nickname == S], None)
        if not source:
            return
        target = next((u for u in self.ircd.users if u.nickname == recv[2] or u.uid == recv[2]), None)
        if not target:
            return
        target.handle('part', ' '.join(recv[3:]))
