def cmd_SVSJOIN(self, localServer, recv):
    if type(self).__name__ != 'Server':
        self.sendraw(487, ':SVSJOIN is a server only command')
        return
    target = list(filter(lambda c: c.uid == recv[2], localServer.users))
    if not target:
        return
    p = {'sajoin': True} 
    target[0].handle('join',recv[3],params=p)
