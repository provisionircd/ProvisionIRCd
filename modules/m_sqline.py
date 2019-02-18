#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/sqline command (server)
"""

import ircd
import time

from handle.functions import TKL

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('sqline')
def sqline(self, localServer, recv):
    nick = recv[2]
    reason = ' '.join(recv[3:])

    if reason.startswith(':'):
        reason = reason[1:]

    data = '+ Q * {} {} 0 {} :{}'.format(nick, self.hostname, int(time.time()), reason)
    self.handle('tkl', data)

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('unsqline')
def unsqline(self, localServer, recv):
    nick = recv[2]
    data = '- Q * {}'.format(nick)
    self.handle('tkl', data)
