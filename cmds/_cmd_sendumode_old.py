def cmd_SENDUMODE(self, localServer, recv):
    if type(self).__name__ != 'Server':
        self.sendraw(487, ':SENDUMODE is a server only command')
        return
    ### 00B SENDUMODE o :message
    users = list(filter(lambda u: recv[2] in u.modes and self != u.server, localServer.users))
    for user in users:
        self.handle('NOTICE', '{} {}'.format(user.uid, ' '.join(recv[3:])))
