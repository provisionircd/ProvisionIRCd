"""
/die command
"""

import ircd
import sys

@ircd.Modules.command
class Die(ircd.Command):
    """
    Shutdown the server remotely.
    """
    def __init__(self):
        self.command = 'die'
        self.req_flags = 'die'

    def execute(self, client, recv):
        if recv[1] != self.ircd.conf['settings']['diepass']:
            client.flood_penalty += 500000
            return client.sendraw(self.ERR.NOPRIVILEGES, ':Permission denied')
        reason = 'Die command received by {} ({}@{})'.format(client.nickname, client.ident, client.hostname)
        msg = '*** {}'.format(reason)
        self.ircd.snotice('s', msg)
        for server in list(self.ircd.servers):
            server._send(':{} SQUIT {} :{}'.format(self.ircd.hostname, self.ircd.hostname, reason))

        for user in [user for user in self.ircd.users if user.server == self.ircd]:
            user.quit(reason=None)

        self.ircd.running = 0

        for s in self.ircd.listen_socks:
            try:
                s.shutdown(socket.SHUT_WR)
            except:
                pass
            s.close()
        sys.exit()
