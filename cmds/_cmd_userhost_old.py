def cmd_USERHOST(self, localServer, recv):
    if len(recv) < 2:
        return self.sendraw(461, ':USERHOST Not enough parameters')
    hosts = []
    for nick in recv[1:]:
        users = filter(lambda u: u.nickname.lower() == nick.lower() and u.registered, localServer.users)
        for user in users:
            h = '{}*=+{}@{}'.format(user.nickname,user.ident,user.cloakhost if 'o' not in self.modes else user.hostname)
            if h not in hosts:
                hosts.append(h)
    self.sendraw(302, ':{}'.format(' '.join(hosts)))
