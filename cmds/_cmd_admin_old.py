def cmd_ADMIN(self, localServer, recv):
    try:
        localServer.conf['admin']
        self.sendraw(256,':Administrative info about {}'.format(localServer.hostname))
        for line in localServer.conf['admin']:
            self.sendraw(257,':{}'.format(line))
    except:
        self.sendraw(421, 'ADMIN :Unknown command you foolish user')
