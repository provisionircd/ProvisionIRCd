"""
/wallops command
"""

import ircd

@ircd.Modules.user_modes('w', 1, 'Can read wallop messages') ### ('mode', 0, 1 or 2 for normal user, oper or server, 'Mode description')
@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('wallops')
@ircd.Modules.commands('wallops')
def wallops(self, localServer, recv):
    if type(self).__name__ == 'Server':
        originServer = self
        source = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
        sourceID = source.uid
        recv = recv[1:]
        msg = ' '.join(recv[1:])[1:]
    else:
        msg = None
        source = self
        originServer = self.server
        sourceID = self.uid

    if not msg:
        msg = ' '.join(recv[1:])
    for user in [user for user in localServer.users if 'w' in user.modes]:
        user._send(':{}!{}@{} WALLOPS :{}'.format(source.nickname, source.ident, source.cloakhost, msg))

    data = ':{} WALLOPS :{}'.format(sourceID, msg)
    localServer.new_sync(localServer, originServer, data)
