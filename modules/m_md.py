"""
/md command (server)
"""

import ircd


@ircd.Modules.command
class Md(ircd.Command):
    def __init__(self):
        self.command = 'md'
        self.req_class = 'Server'
        self.params = 3

    def execute(self, client, recv):
        ### :irc.foonet.com MD client 001HBEI01 certfp :a6fc0bd6100a776aa3266ed9d5853d6dce563560d8f18869bc7eef811cb2d413
        if recv[2] == 'client':
            user = list(filter(lambda u: u.uid == recv[3], self.ircd.users))
            if user == []:
                return
            if recv[4] == 'certfp':
                user[0].fingerprint = recv[5][1:]
                # print('SSL fingerprint for remote user {} set: {}'.format(user[0].nickname, user[0].fingerprint))
            elif recv[4] == 'operaccount':
                user[0].operaccount = recv[5][1:]
                # print('Oper account for remote user {} set: {}'.format(user[0].nickname, user[0].operaccount))

        self.ircd.new_sync(self.ircd, client, ' '.join(recv))
