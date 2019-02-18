def cmd_USER(self, localServer, recv):
    if type(self).__name__ == 'Server':
        _self = self
        self = list(filter(lambda u: u.uid == recv[0][1:], localServer.users))
        if not self:
            _self.quit('This port is for servers only', error=True)
            return

    if len(recv) < 5:
        self.sendraw(461, ':USER Not enough parameters')
        return

    if self.ident:
        self.sendraw(462, ':You may not reregister')
        return

    if 'nmap' in ''.join(recv).lower():
        self.quit('Connection reset by peer')
        return

    ident = recv[1][:12]
    realname = recv[4][:48]

    valid = "abcdefghijklmnopqrstuvwxyz0123456789.-_"
    for c in ident:
        if c.lower() not in valid:
            ident = ident.replace(c, '')

    self.ident = ident
    self.realname = realname
    if self.nickname != '*' and self.validping:
        self.welcome()
