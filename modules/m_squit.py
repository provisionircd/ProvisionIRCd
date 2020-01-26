"""
/squit command (server)
"""

import ircd

from handle.functions import logging

W = '\033[0m'  # white (normal)
R = '\033[31m' # red

@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('squit')
@ircd.Modules.commands('squit')
def squit(self, localServer, recv):
    if type(self).__name__ == 'Server':
        source = [s for s in localServer.servers if s.sid == recv[0][1:]]
        if not source:
            logging.error('{}ERROR: source for SID {} could not be found. Was it already removed?{}'.format(R, recv[0][1:], W))
            source = self
        else:
            source = source[0]
        server = list(filter(lambda s: s.sid.lower() == recv[2].lower() or s.hostname.lower() == recv[2].lower(), localServer.servers))
        if not server:
            logging.error('{}ERROR: server for {} could not be found. Was it already removed?{}'.format(R, recv[2], W))
            return
        server = server[0]
        localServer.new_sync(localServer, self, ' '.join(recv))
        server.quit(' '.join(recv[3:]), source=source, squit=False)
        return

    reason = '[{}] {}'.format(self.nickname,' '.join(recv[2:]))

    name = recv[1]

    server = list(filter(lambda s: s.hostname.lower() == name.lower(), localServer.servers))
    if server:
        server = server[0]

    if not [server for server in localServer.servers if server.hostname == name]:
        localServer.notice(self, '*** Currently not connected to {}'.format(name))
        return

    msg = '*** {} ({}@{}) used SQUIT command for {}: {}'.format(self.nickname, self.ident, self.hostname, server.hostname, reason)
    localServer.snotice('s', msg)
    server.quit(reason)
