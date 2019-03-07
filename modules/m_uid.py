#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/uid command (server)
"""

import ircd

from handle.functions import logging

W = '\033[0m'  # white (normal)
R = '\033[31m' # red

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('uid')
def uid(self, localServer, recv):
    try:
        nick = recv[2]
        params = []
        for p in recv:
            params.append(p)
        for user in [user for user in localServer.users if user.nickname.lower() == nick.lower()]:
            logging.error('Found double user in UID: {}'.format(user))
            if not user.server:
                logging.error('Quitting {} because their server could not be found (UID)'.format(user))
                user.quit('Unknown or corrupted connection with the same nick')
                continue
            logging.error('{}ERROR: user {} already found on the network{}'.format(R, user, W))
            localUserClass = list(filter(lambda c: c.nickname.lower() == user.nickname.lower() and c.server.hostname == localServer.hostname, localServer.users))
            if localUserClass:
                localUserClass = localUserClass[0]
                localTS = int(localUserClass.signon)
                remoteTS = int(recv[4])
                if remoteTS <= localTS:
                    logging.info('{}Local user {} disconnected from local server.{}'.format(R, localUserClass, W))
                    localUserClass.quit('Local Nick Collision', silent=True)
                else:
                    user.quit('Remote Nick Collision', silent=True)

        u = ircd.User(self, serverClass=localServer, params=params)
        cmd = ' '.join(recv)
        localServer.new_sync(localServer, self, cmd)
    except Exception as ex:
        logging.exception(ex)
