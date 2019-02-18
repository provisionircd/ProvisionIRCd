
    def stealthOn(self, override=False):
        localServer = self.server if self.socket else self.origin
        for channel in self.channels:
            users = list(filter(lambda u: u != self and (not u.ocheck('o', 'stealth') and not override) and u.server == localServer, channel.users))
            self.broadcast(users, 'PART {}'.format(channel.name))
            users = list(filter(lambda u: u.ocheck('o', 'stealth'), channel.users))
            removeModes = ''
            for m in channel.usermodes[self]:
                removeModes += m
            channel.usermodes[self] = 'y'
            self.server.broadcast(users, 'MODE {} +y{} {}'.format(channel.name, '-{}{}'.format(removeModes, ' {}'.format(self.nickname)*len(removeModes)) if removeModes else '', self.nickname))

    def stealthOff(self, override=False):
        localServer = self.server if self.socket else self.origin
        for channel in self.channels:
            users = list(filter(lambda u: u != self and (not u.ocheck('o', 'stealth') and not override), channel.users))
            channel.usermodes[self] = ''
            self.broadcast(users, 'JOIN {}'.format(channel.name))
            channel.usermodes[self] = channel.usermodes[self].replace('y', '')
            localServer.syncToServers(localServer, self.server, ':{} SJOIN {} {}{} :{}'.format(self.server.sid, int(time.time()), channel.name, ' +{}'.format(channel.modes) if channel.modes else '', self.uid))
            users = list(filter(lambda u: u.ocheck('o', 'stealth'), channel.users))
            self.server.broadcast(users, 'MODE {} -y {}'.format(channel.name, self.nickname))