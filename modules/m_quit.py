#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/quit command
"""

import ircd

@ircd.Modules.commands('quit')
def quit(self, localServer, recv, showPrefix=True):
    source = None
    if type(self).__name__ == 'Server':
        source = self
        showPrefix = False
        if not self.eos:
            return
        self = list(filter(lambda u: u.uid == recv[0][1:], localServer.users))
        if not self:
            ### User is already disconnected.
            return
        else:
            self = self[0]

        recv = recv[1:]

    if len(recv) > 1:
        reason = ' '.join(recv[1:][:128])
        if reason.startswith(':'):
            reason = reason[1:]
    else:
        reason = self.nickname

    try:
        quitprefix = str(localServer.conf['settings']['quitprefix']).strip()

        if quitprefix.endswith(':'):
            quitprefix = quitprefix[:-1]
    except:
        quitprefix = 'Quit'

    if 'static-quit' in localServer.conf['settings'] and localServer.conf['settings']['static-quit']:
        reason = localServer.conf['settings']['static-quit']

    reason = '{}{}'.format(quitprefix+': ' if self.server == localServer and showPrefix else '', reason)

    self.quit(reason, error=False)
