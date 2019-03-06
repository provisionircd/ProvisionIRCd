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
        for user in [user for user in localServer.users if user.nickname.lower() == nick.lower()]:
            _print('Found double user in UID: {}'.format(user), server=localServer)
            if not user.server:
                _print('Quitting {} because their server could not be found (UID)'.format(user), server=localServer)
                user.quit('Unknown or corrupted connection with the same nick')
                continue
            _print('{}WARNING: user {} already found on the network{}'.format(R, user, W), server=localServer)
            localUserClass = list(filter(lambda c: c.nickname.lower() == user.nickname.lower() and c.server.hostname == localServer.hostname, localServer.users))
            if localUserClass:
                localUserClass = localUserClass[0]
                localTS = int(localUserClass.signon)
                remoteTS = int(recv[4])
                if remoteTS <= localTS:
                    _print('{}Local user {} disconnected from local server.{}'.format(R, localUserClass, W), server=localServer)
                    localUserClass.quit('Local Nick Collision', silent=True)
                else:
                    user.quit('Remote Nick Collision', silent=True)

        _print('Creating local class for remote user', server=localServer)
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
