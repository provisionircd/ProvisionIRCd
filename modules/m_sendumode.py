"""
/sendumode command (server)
"""

import ircd

@ircd.Modules.command
class Sendumode(ircd.Command):
    def __init__(self):
        self.command = 'sendumode'
        self.params = 2
        self.req_class = 'Server'

    def execute(self, client, recv):
        ### 00B SENDUMODE o :message
        source = list(filter(lambda s: s.sid == recv[0][1:], self.ircd.servers))[0]
        for user in [user for user in self.ircd.users if recv[2] in user.modes and user.socket]:
            source.broadcast([user], 'NOTICE {} {}'.format(user.nickname, ' '.join(recv[3:])))
        self.ircd.new_sync(self.ircd, client, ' '.join(recv))
