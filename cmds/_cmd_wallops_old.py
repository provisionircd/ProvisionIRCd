import os, sys

def cmd_WALLOPS(self, localServer, recv, override=False):
    if type(self).__name__ == 'Server':
        override = True
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

    if not override:
        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return
        if not self.ocheck('o', 'wallops'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return
        if len(recv) < 2:
            self.sendraw(461, ':WALLOPS Not enough parameters')
            return
    if not msg:
        msg = ' '.join(recv[1:])
    for user in [user for user in localServer.users if 'o' in user.modes and 'w' in user.modes]:
        user._send(':{}!{}@{} WALLOPS :{}'.format(source.nickname, source.ident, source.cloakhost, msg))

    data = ':{} WALLOPS :{}'.format(sourceID, msg)
    localServer.syncToServers(localServer, originServer, data)
