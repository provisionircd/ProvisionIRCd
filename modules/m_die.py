"""
/die command
"""

import ircd
import os


class Die(ircd.Command):
    """
    Shutdown the server remotely.
    """
    def __init__(self):
        self.command = 'die'
        self.params = 1
        self.req_flags = 'die'

    def execute(self, client, recv):
        if recv[1] != self.ircd.conf['settings']['diepass']:
            client.flood_penalty += 2500001
            return client.sendraw(self.ERR.NOPRIVILEGES, ':Permission denied')

        reason = 'DIE command received by {} ({}@{})'.format(client.nickname, client.ident, client.hostname)
        msg = '*** {}'.format(reason)
        self.ircd.snotice('s', msg)

        for user in [user for user in self.ircd.users if user.server == self.ircd]:
            user.quit(reason=None)

        for server in list(self.ircd.servers):
            server._send(':{} SQUIT {} :{}'.format(self.ircd.hostname, self.ircd.hostname, reason))

        os._exit(os.getpid())
