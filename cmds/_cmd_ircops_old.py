def cmd_IRCOPS(self, localServer, recv):
    self.sendraw(386,':§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
    self.sendraw(386,':Nick                  Status      Server')
    self.sendraw(386,':--------------------------------------------')
    globalModes = 'N'
    globals, aways, opers = 0, 0, 0
    for oper in [user for user in self.server.users if 'o' in user.modes and ('H' not in user.modes or 'o' in self.modes) and 'S' not in user.modes]:
        opers += 1
        if 'o' in oper.modes or oper.modes in globalModes:
            globals += 1
        if oper.away:
            aways += 1
        self.sendraw(386,':{}{}{}{}{}{}'.format(oper.nickname,' '*(22-int(len(oper.nickname))),'Oper' if 'A' not in oper.modes or 'N' not in oper.modes else 'Admin',' (AWAY)' if oper.away else '',' '*9 if not oper.away else ' '*2 ,oper.server.hostname))
    self.sendraw(386,':Total: {} IRCOP{} connected - {} Global, and {} Away'.format(opers,'s' if opers != 1 else '',globals,aways))
    self.sendraw(386,':§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
    self.sendraw(386,':End of /IRCOPS.')
