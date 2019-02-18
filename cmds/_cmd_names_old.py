def cmd_NAMES(self, localServer, recv):
    if len(recv) < 2:
        self.sendraw(461, ':NAMES Not enough parameters')
        return

    channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), localServer.channels))
    if channel == []:
        self.sendraw(401, '{} :No such channel'.format(recv[1]))
        return

    channel = channel[0]

    users = []

    for user in channel.users:
        if 'i' in user.modes and (self not in channel.users and not self.ocheck('o', 'override')):
            continue
        if '^' in user.modes:
            if not self.ocheck('o', 'stealth'):
                continue
            else:
                users.append('!'+user.nickname)
            continue

        prefix = ''
        for mode in localServer.chprefix:
            if mode in channel.usermodes[user]:
                prefix += localServer.chprefix[mode]

        users.append(prefix+''+user.nickname)

        if len(users) >= 24:
            self.sendraw(353, '= {} :{}'.format(channel.name, ' '.join(users)))
            users = []
            continue

    self.sendraw(353, '= {} :{}'.format(channel.name, ' '.join(users)))
    self.sendraw(366, '{} :End of /NAMES list.'.format(channel.name))
