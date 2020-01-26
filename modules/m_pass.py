"""
/pass command (server)
"""

import ircd

from handle.functions import logging

@ircd.Modules.params(1)
@ircd.Modules.commands('pass')
def cmd_pass(self, localServer, recv):
    """Used by servers to authenticate themselves during linking process."""
    source = recv[0][1:]
    if type(self).__name__ == 'User':
        if self.registered:
            return self.sendraw(462, ':You may not reregister')
        # Check for server password.
        if 'password' in localServer.conf['allow'][self.cls]:
            if recv[1] == localServer.conf['allow'][self.cls]['password']:
                self.server_pass_accepted = 1
                logging.info('Server password accepted for {}'.format(self))
                return
            else:
                return self.quit('Invalid password')

    if type(self).__name__ == 'Server' and 'link' not in localServer.conf:
        return self.quit('Target has no links configured')

    if len(recv) < 3:
        return
    self.linkpass = recv[2][1:]
    logging.info('Password for {} set: {}'.format(self, self.linkpass))
    ip, port = self.socket.getpeername()
    ip2, port2 = self.socket.getsockname()

    if self.hostname:
        if self.hostname not in localServer.conf['link']:
            msg = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(self.hostname, ip, port)
            error = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(localServer.hostname, ip2, port2)
            if self not in localServer.linkrequester:
                self._send('ERROR :{}'.format(error))
            elif localServer.linkrequester[self]['user']:
                localServer.linkrequester[self]['user'].send('NOTICE', '*** {}'.format(msg))
            self.quit('no matching link configuration', silent=True)
            return

        if self.linkpass != localServer.conf['link'][self.hostname]['pass']:
            msg = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(self.hostname, ip, port)
            error = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(localServer.hostname, ip2, port2)
            if self not in localServer.linkrequester:
                self._send('ERROR :{}'.format(error))
            elif localServer.linkrequester[self]['user']:
                localServer.linkrequester[self]['user'].send('NOTICE', '*** {}'.format(msg))
            self.quit('no matching link configuration', silent=True)
            return
