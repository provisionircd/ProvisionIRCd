"""
/svskill command (server)
"""

import ircd


@ircd.Modules.command
class Svskill(ircd.Command):
    def __init__(self):
        self.params = 2
        self.req_class = 'Server'
        self.command = 'svskill'

    def execute(self, client, recv):
        client = next((u for u in self.ircd.users if u.nickname == recv[0][1:] or u.uid == recv[0][1:]), None)
        # self = list(filter(lambda u: u.nickname.lower() == recv[0][1:].lower() or u.uid.lower() == recv[0][1:].lower(), self.ircd.users))
        if not client:
            # Maybe it is a server?
            # self = list(filter(lambda s: s.hostname.lower() == recv[0][1:].lower() or s.sid.lower() == recv[0][1:].lower(), self.ircd.servers))
            client = next((s for s in self.ircd.servers if s.hostname == recv[0][1:] or s.sid == recv[0][1:]), None)
            if not client:
                return
            else:
                sourceID = client.sid
        else:
            sourceID = client.uid

        recv = recv[1:]
        # target = list(filter(lambda u: u.nickname.lower() == recv[1].lower() or u.uid.lower() == recv[1].lower(), self.ircd.users))
        target = next((u for u in self.ircd.users if u.nickname == recv[1] or u.uid == recv[1]), None)
        if not target:
            return
        reason = ' '.join(recv[2:])[1:]

        data = ':{} SVSKILL {} :{}'.format(sourceID, target.uid, reason)

        if target.server != self.ircd:
            target.server._send(data)

        target.quit(reason, kill=True)
