#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/setname command
"""

import ircd
import sys
import os

@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.commands('setname')
def setname(self, localServer, recv):
    if type(self).__name__ == 'Server':
        sourceServer = self
        self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))
        if not self:
            return
        self = self[0]
        recv = recv[1:]
        realname = ' '.join(recv[1:]).rstrip()[1:]
        self.realname = realname
        localServer.new_sync(localServer, sourceServer, ':{} SETNAME :{}'.format(self.uid, self.realname))
        return

    realname = ' '.join(recv[1:])[:48].rstrip()
    if realname and realname != self.realname:
        self.realname = realname
        localServer.notice(self, '*** Your realname is now "{}"'.format(self.realname))
        localServer.new_sync(localServer, self.server, ':{} SETNAME :{}'.format(self.uid, self.realname))
