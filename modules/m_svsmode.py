#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/svsmode and /svs2mode command (server)
"""

import ircd

from handle.functions import _print

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('svsmode', 'svs2mode')
def svsmode(self, localServer, recv):
    source = list(filter(lambda c: c.uid == recv[0][1:], localServer.users))
    ### Source can also be a server, you lazy fuck.
    if not source:
        return
    source = source[0]
    target = list(filter(lambda u: u.uid == recv[2] or u.nickname == recv[2], localServer.users))
    if not target:
        return
    target = target[0]
    action = ''
    modes = ''
    paramcount = 4
    for m in recv[3]:
        if m in '+-' and m != action:
            action = m
            modes += action
            continue
        elif m != 'd' and m not in localServer.user_modes:
            continue
        if action == '+':
            if m == 'd':
                try:
                    svid = recv[paramcount]
                    if str(svid) != '0':
                        target.svid = svid
                    else:
                        target.svid = '*'
                    updated = []
                    for user in localServer.users:
                        for user in [user for user in localServer.users if 'account-notify' in user.caplist and user not in updated and user.socket]:
                            common_chan = list(filter(lambda c: user in c.users and target in c.users, localServer.channels))
                            if not common_chan:
                                continue
                            user._send(':{} ACCOUNT {}'.format(target.fullmask(), target.svid))
                            updated.append(user)
                    continue
                except:
                    pass
            if recv[1].lower() == 'svsmode':
                target.modes += m
            modes += m
        elif action == '-':
            if recv[1].lower() == 'svsmode':
                target.modes = target.modes.replace(m, '')
            modes += m
    if recv[1].lower() == 'svs2mode':
        source.handle('mode', '{} {}'.format(target.nickname, modes))

    data = ' '.join(recv)
    localServer.new_sync(localServer, self, data)
    #localServer.syncToServers(localServer, source.server, data)
