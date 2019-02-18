def cmd_CLONES(self, localServer, recv):
    ### Deze is lastig.
    clones, foundclones = [], False
    for user in localServer.users:
        if user.ip not in clones:
            clones.append(user.ip)
            logins = list(filter(lambda u: u.ip == user.ip and (u.server.hostname not in localServer.conf['settings']['ulines'] and 'S' not in u.modes) and user.registered, localServer.users))
            if len(logins) > 1:
                foundclones = True
                nicks = []
                for user in logins:
                    nicks.append(user.nickname)
                self.sendraw(501, ':User {} is logged in {} times: {}'.format(user.nickname, len(logins), ' '.join(nicks)))

    if not foundclones:
        self.sendraw(501, ':No clones found on this {}.'.format('server' if not localServer.servers else 'network'))

            ### Ik moet nadenken :( kutleven.  sec, wat fix je dan ? simpele /clones cmd
