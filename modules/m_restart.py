"""
/restart command
"""

import os
import sys

import ircd


class Restart(ircd.Command):
    """
    Restart the server remotely.
    """

    def __init__(self):
        self.command = 'restart'
        self.params = 1
        self.req_flags = 'restart'

    def execute(self, client, recv):
        if recv[1] != self.ircd.conf['settings']['restartpass']:
            client.flood_penalty += 2500001
            return client.sendraw(self.ERR.NOPRIVILEGES, ':Permission denied')

        reason = 'RESTART command received by {} ({}@{})'.format(client.nickname, client.ident, client.hostname)
        msg = '*** {}'.format(reason)
        self.ircd.snotice('s', msg)

        for user in [user for user in self.ircd.users if user.server == self.ircd]:
            user.quit(reason=None)

        for server in list(self.ircd.servers):
            server._send(':{} SQUIT {} :{}'.format(self.ircd.hostname, self.ircd.hostname, reason))

        python = sys.executable
        os.execl(python, python, *sys.argv)
