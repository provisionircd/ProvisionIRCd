from handle.functions import checkSpamfilter

def cmd_AWAY(self, localServer, recv, override=False):
    if type(self).__name__ == 'Server':
        override = True
        self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
        data = ' '.join(recv)
        recv = recv[1:]
        sourceServer = self
    else:
        data = ':{} {} :{}'.format(self.uid, ''.join(recv[0]), ' '.join(recv[1:]))
        sourceServer = self.server

    if len(recv) < 2:
        self.away = False
        self.sendraw(305, ':You are no longer marked as being away')
    else:
        away = ' '.join(recv[1:])[:localServer.awaylen]

        if checkSpamfilter(self, localServer, self.nickname, 'away', away):
            return

        self.away = away
        if self.away.startswith(':'):
            self.away = self.away[1:]
        self.sendraw(306, ':You have been marked as being away')

    localServer.syncToServers(localServer, sourceServer, data)
