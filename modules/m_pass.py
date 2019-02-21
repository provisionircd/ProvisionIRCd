#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/pass command (server)
"""

import ircd

from handle.functions import _print

@ircd.Modules.params(1)
@ircd.Modules.commands('pass')
def cmd_pass(self, localServer, recv):
    source = recv[0][1:]
    if type(self).__name__ == 'User' and self.registered:
        return self.sendraw(462, ':You may not reregister')

    self.linkpass = recv[2][1:]
    _print('Password for {} set: {}'.format(self, self.linkpass), server=localServer)
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
