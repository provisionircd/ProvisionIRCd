#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/svsjoin and /svspart command (server)
"""

import ircd

@ircd.Modules.params(2)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('svsjoin')
def svsjoin(self, localServer, recv):
    S = recv[0][1:]
    source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
    if not source:
        return
    source = source[0]
    target = list(filter(lambda c: c.uid == recv[2], localServer.users))
    if not target:
        return
    p = {'sajoin': True}
    target[0].handle('join', recv[3], params=p)

@ircd.Modules.params(2)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('svspart')
def svspart(self, localServer, recv):
    S = recv[0][1:]
    source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
    if not source:
        return
    source = source[0]
    target = list(filter(lambda c: c.uid == recv[2], localServer.users))
    if not target:
        return
    p = {'sapart': source}
    target[0].handle('part', recv[3], params=p)
