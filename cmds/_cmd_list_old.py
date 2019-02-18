def cmd_LIST(self, localServer, recv):
    self.sendraw(321,'Channel :Users  Name')
    for channel in localServer.channels:
        if 's' in channel.modes and (self not in channel.users and not self.ocheck('o', 'override')):
            continue
        if 'p' in channel.modes and (self not in channel.users and not self.ocheck('o', 'override')):
            self.sendraw(322, '* {} :'.format(channel.name, len(channel.users)))
        else:
            self.sendraw(322, '{} {} :[+{}] {}'.format(channel.name, len(channel.users) ,channel.modes, channel.topic))
    self.sendraw(323, ':End of /LIST')
