"""
/clones command
"""

import ircd


class Clones(ircd.Command):
    def __init__(self):
        self.command = 'clones'
        self.req_modes = 'o'

    def execute(self, client, recv):
        clones, foundclones = [], False
        for user in self.ircd.users:
            if user.ip not in clones:
                clones.append(user.ip)
                logins = list(filter(lambda u: u.ip == user.ip and (u.server.hostname not in self.ircd.conf['settings']['ulines'] and 'S' not in u.modes) and user.registered, self.ircd.users))
                if len(logins) > 1:
                    foundclones = True
                    nicks = []
                    for user in logins:
                        nicks.append(user.nickname)
                    client.sendraw('030', ':User {} is logged in {} times: {}'.format(user.nickname, len(logins), ' '.join(nicks)))

        if not foundclones:
            client.sendraw('031', ':No clones found on this {}.'.format('server' if not self.ircd.servers else 'network'))
