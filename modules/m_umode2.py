#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/umode2 command (server)
"""

import ircd

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('umode2')
def umode2(self, localServer, recv):
    ### :asdf UMODE2 +ot
    target = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
    modeset = None
    for m in recv[2]:
        if m in '+-':
            modeset = m
            continue
        if modeset == '+':
            if m not in target.modes:
                target.modes += m

        elif modeset == '-':
            target.modes = target.modes.replace(m, '')
            if m == 'o':
                target.operflags = []
                target.swhois = []
                target.opermodes = ''
            elif m == 's':
                target.snomasks = ''

    localServer.new_sync(localServer, self, ' '.join(recv))
