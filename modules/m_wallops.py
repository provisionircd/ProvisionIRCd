"""
/wallops command
"""

import ircd


@ircd.Modules.user_mode
class umode_w(ircd.UserMode):
    def __init__(self):
        self.mode = 'w'
        self.desc = 'Can read wallop messages'
        self.req_flag = 1


@ircd.Modules.command
class Wallops(ircd.Command):
    def __init__(self):
        self.command = 'wallops'
        self.params = 1
        self.req_flags = 'wallops'

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            originServer = client
            source = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], self.ircd.users))[0]
            sourceID = source.uid
            recv = recv[1:]
            msg = ' '.join(recv[1:])[1:]
        else:
            msg = None
            source = client
            originServer = client.server
            sourceID = client.uid

        if not msg:
            msg = ' '.join(recv[1:])
        for user in [user for user in self.ircd.users if 'w' in user.modes]:
            user._send(':{}!{}@{} WALLOPS :{}'.format(source.nickname, source.ident, source.cloakhost, msg))

        data = ':{} WALLOPS :{}'.format(sourceID, msg)
        self.ircd.new_sync(self.ircd, originServer, data)
