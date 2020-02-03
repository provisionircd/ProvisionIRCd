"""
/squit command (server)
"""

import ircd

from handle.functions import logging

W = '\033[0m'  # white (normal)
R = '\033[31m' # red

@ircd.Modules.command
class Squit(ircd.Command):
    def __init__(self):
        self.command = 'squit'
        self.params = 2
        self.req_flags = 'squit'


    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            source = [s for s in self.ircd.servers if s.sid == recv[0][1:]]
            if not source:
                logging.error('{}ERROR: source for SID {} could not be found. Was it already removed?{}'.format(R, recv[0][1:], W))
                source = client
            else:
                source = source[0]
            server = list(filter(lambda s: s.sid.lower() == recv[2].lower() or s.hostname.lower() == recv[2].lower(), self.ircd.servers))
            if not server:
                logging.error('{}ERROR: server for {} could not be found. Was it already removed?{}'.format(R, recv[2], W))
                return
            server = server[0]
            self.ircd.new_sync(self.ircd, client, ' '.join(recv))
            server.quit(' '.join(recv[3:]), source=source, squit=False)
            return

        reason = '[{}] {}'.format(client.nickname,' '.join(recv[2:]))

        name = recv[1]

        server = list(filter(lambda s: s.hostname.lower() == name.lower(), self.ircd.servers))
        if server:
            server = server[0]

        if not [server for server in self.ircd.servers if server.hostname == name]:
            self.ircd.notice(client, '*** Currently not connected to {}'.format(name))
            return

        msg = '*** {} ({}@{}) used SQUIT command for {}: {}'.format(client.nickname, client.ident, client.hostname, server.hostname, reason)
        self.ircd.snotice('s', msg)
        server.quit(reason)
