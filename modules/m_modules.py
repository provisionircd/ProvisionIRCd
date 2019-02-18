#!/usr/bin/env python

"""
show modules with /modules
"""

import ircd

@ircd.Modules.req_modes('o')
@ircd.Modules.commands('modules')
def modules(self, localServer, recv):
    for m in localServer.modules:
        info = m.__doc__
        cmds = ''
        if info:
            info = ' '.join(m.__doc__.split('\n'))
        for c in localServer.commands:
            if c[5] == m:
                print('Module {} is a command'.format(m))
                cmds += '{}'.format(', ' if cmds else '') + '/'+c[0]
        #if cmds:
        #    info = '{}{}'.format(info if info else '', '(Command: {})'.format(cmds))

        msg = '* {}{}'.format(m.__name__, ' -- {}'.format(info) if info else '')
        self._send(':{} NOTICE {} :{}'.format(localServer.hostname, self.nickname, msg))
