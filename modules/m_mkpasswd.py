#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/mkpasswd command
"""

import ircd
import bcrypt

@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.commands('mkpasswd')
def mkpasswd(self, localServer, recv):
    if len(recv[1]) == 1:
        return localServer.notice(self, '*** Really? You think that is secure?')

    if len(recv[1]) < 8:
        return localServer.notice(self, '*** Given password is too short.')

    self.flood_penalty += 10000
    hashed = bcrypt.hashpw(recv[1].encode('utf-8'),bcrypt.gensalt(10)).decode('utf-8')
    localServer.notice(self, '*** Hashed ({}): {}'.format(recv[1], hashed))

