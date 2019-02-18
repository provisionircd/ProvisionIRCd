
def cmd_SVSNICK(self, localServer, recv):
    if type(self).__name__ != 'Server':
        self.sendraw(487, ':SVSNICK is a server only command')
        return
    target = list(filter(lambda u: u.uid == recv[2] or u.nickname == recv[2], localServer.users))
    if not target:
        return

    p = {'sanick': True}
    target[0].handle('nick', recv[3], params=p)
