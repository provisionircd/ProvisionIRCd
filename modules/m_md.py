#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/md command (server)
"""

import ircd

@ircd.Modules.params(6)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('md')
def md(self, localServer, recv):
    ### :irc.foonet.com MD client 001HBEI01 certfp :a6fc0bd6100a776aa3266ed9d5853d6dce563560d8f18869bc7eef811cb2d413
    if recv[2] == 'client':
        user = list(filter(lambda u: u.uid == recv[3], localServer.users))
        if user == []:
            return
        if recv[4] == 'certfp':
            user[0].fingerprint = recv[5][1:]
            #print('SSL fingerprint for remote user {} set: {}'.format(user[0].nickname, user[0].fingerprint))
        elif recv[4] == 'operaccount':
            user[0].operaccount = recv[5][1:]
            #print('Oper account for remote user {} set: {}'.format(user[0].nickname, user[0].operaccount))

    localServer.new_sync(localServer, self, ' '.join(recv))
