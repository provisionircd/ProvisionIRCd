#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/sendumode command (server)
"""

import ircd

@ircd.Modules.params(2)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('sendumode')
def sendumode(self, localServer, recv):
    ### 00B SENDUMODE o :message
    source = list(filter(lambda s: s.sid == recv[0][1:], localServer.servers))[0]
    for user in [user for user in localServer.users if recv[2] in user.modes and user.socket]:
        source.broadcast([user], 'NOTICE {} {}'.format(user.nickname, ' '.join(recv[3:])))

    localServer.new_sync(localServer, self, ' '.join(recv))
