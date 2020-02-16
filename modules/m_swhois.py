"""
/swhois command (server)
"""

import ircd

@ircd.Modules.command
class Swhois(ircd.Command):
    def __init__(self):
        self.params = 2
        self.req_class = 'Server'
        self.command = 'swhois'

    def execute(self, client, recv):
        ### :source SWHOIS target :line
        ### :source SWHOIS target :
        user = list(filter(lambda u: u.uid == recv[2] or u.nickname == recv[2], self.ircd.users))
        if not user:
            return
        user = user[0]
        swhois = ' '.join(recv[3:])[1:] if recv[3].startswith(':') else ' '.join(recv[3:])
        if swhois:
            if swhois not in user.swhois:
                user.swhois.append(swhois)
        else:
            user.swhois = []

        self.ircd.new_sync(self.ircd, client, ' '.join(recv))
