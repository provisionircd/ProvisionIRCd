"""
/uid command (server)
"""

import ircd

from handle.functions import logging

W = '\033[0m'  # white (normal)
R = '\033[31m'  # red


@ircd.Modules.command
class Uid(ircd.Command):
    def __init__(self):
        self.command = 'uid'
        self.req_class = 'Server'

    def execute(self, client, recv):
        nick = recv[2]
        params = []
        allow = 1
        for p in recv:
            params.append(p)
        for user in [user for user in self.ircd.users if user.nickname.lower() == nick.lower()]:
            logging.error('Found double user in UID: {}'.format(user))
            if not user.server:
                logging.error('Quitting {} because their server could not be found (UID)'.format(user))
                user.quit('Unknown or corrupted connection with the same nick')
                continue
            logging.error('{}ERROR: user {} already found on the network{}'.format(R, user, W))
            localTS = int(user.signon)
            remoteTS = int(recv[4])
            if remoteTS <= localTS:
                logging.info('{}Local user {} disconnected from local server.{}'.format(R, user, W))
                user.quit('Local Nick Collision', silent=True)
                continue
            else:
                allow = 0
                logging.debug('Disallowing remote user {}'.format(user))
                return
        if allow:
            u = ircd.User(client, server_class=self.ircd, params=params)
            cmd = ' '.join(recv)
            self.ircd.new_sync(self.ircd, client, cmd)
