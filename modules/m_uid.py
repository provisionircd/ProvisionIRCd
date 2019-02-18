#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/uid command (server)
"""

import ircd
import os
import sys

from handle.functions import match, _print, TKL
from handle.handleLink import syncData, selfIntroduction

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
G = '\033[32m' # green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('uid')
def uid(self, localServer, recv):
    try:
        nick = recv[2]
        params = []
        for p in recv:
            params.append(p)
        if nick.lower() in [user.nickname.lower() for user in localServer.users] and not self.eos:
            user = list(filter(lambda c: c.nickname.lower() == nick.lower(), localServer.users))[0]
            _print('{}WARNING: user {} already found on {}{}'.format(R, user.nickname, user.server.hostname, W), server=localServer)
            localUserClass = list(filter(lambda c: c.nickname.lower() == nick.lower() and c.server.hostname == localServer.hostname, localServer.users))[0]
            localTS = int(localUserClass.signon)
            remoteTS = int(recv[4])
            if remoteTS <= localTS:
                _print('{}Local user {} disconnected from local server.{}'.format(R, localUserClass.nickname, W), server=localServer)
                localUserClass.quit('Local Nick Collision', silent=True)

        u = ircd.User(self, serverClass=localServer, params=params)

        TKL.check(self, localServer, u, 'Z')
        TKL.check(self, localServer, u, 'K')

        cmd = ' '.join(recv)
        localServer.new_sync(localServer, self, cmd)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
