def cmd_ISON(self, localServer, recv):
    if len(recv) < 2:
        return self.sendraw(461, ':ISON Not enough parameters')
    nicks = []
    for nick in recv[1:]:
        users = filter(lambda u: u.nickname.lower() == nick.lower() and u.registered, localServer.users)
        for user in [user for user in users if user.nickname not in nicks]:
            nicks.append(user.nickname)
    self.sendraw(303, ':{}'.format(' '.join(nicks)))
