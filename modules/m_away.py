#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/away command
"""

import ircd

from handle.functions import checkSpamfilter

awaylen = 307

@ircd.Modules.support('AWAYLEN='+str(awaylen))
@ircd.Modules.support('WATCHOPTS=A')
@ircd.Modules.commands('away')
def away(self, localServer, recv, override=False):
    if type(self).__name__ == 'Server':
        sourceServer = self
        self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
        data = ' '.join(recv)
        recv = recv[1:]
    else:
        data = ':{} {} :{}'.format(self.uid, ''.join(recv[0]), ' '.join(recv[1:]))
        sourceServer = self.server

    if len(recv) < 2:
        if not self.away:
            return
        self.away = False
        self.sendraw(305, ':You are no longer marked as being away')
    else:
        away = ' '.join(recv[1:])[:awaylen]

        if checkSpamfilter(self, localServer, self.nickname, 'away', away):
            return

        self.away = away
        if self.away.startswith(':'):
            self.away = self.away[1:]
        self.sendraw(306, ':You have been marked as being away')

    updated = []
    for user in localServer.users:
        for user in [user for user in localServer.users if 'away-notify' in user.caplist and user not in updated and user.socket]:
            common_chan = list(filter(lambda c: user in c.users and self in c.users, localServer.channels))
            if not common_chan:
                continue
            user._send(':{} AWAY {}'.format(self.fullmask(), '{}'.format(':'+self.away if self.away else '')))
            updated.append(user)

    localServer.new_sync(localServer, sourceServer, data)
