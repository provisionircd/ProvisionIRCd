#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/setident command
"""

import ircd
import sys
import os

@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.commands('setident')
def setident(self, localServer, recv):
    if type(self).__name__ == 'Server':
        source = self
        self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))
        if not self:
            return
        self = self[0]
        recv = recv[1:]
        ident = str(recv[1]).strip()
        self.setinfo(ident, t='ident', source=source)
        return
    else:
        source = self.server

    ident = str(recv[1][:64]).strip()
    valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
    for c in str(ident):
        if c.lower() not in valid:
            ident = ident.replace(c, '')
    if ident and ident != self.ident:
        self.setinfo(ident, t='ident', source=source)
        localServer.notice(self, '*** Your ident is now "{}"'.format(self.ident))
