"""
show modules with /modules
"""

import ircd


class Modules(ircd.Command):
    def __init__(self):
        self.command = 'modules'
        self.req_modes = 'o'

    def execute(self, client, recv):
        for m in self.ircd.modules:
            info = m.__doc__
            cmds = ''
            if info:
                info = ' '.join(m.__doc__.split('\n'))
            for c in self.ircd.commands:
                if c[5] == m:
                    cmds += '{}'.format(', ' if cmds else '') + '/' + c[0]
            # if cmds:
            #    info = '{}{}'.format(info if info else '', '(Command: {})'.format(cmds))

            msg = '* {}{}'.format(m.__name__, ' -- {}'.format(info) if info else '')
            client._send(':{} NOTICE {} :{}'.format(self.ircd.hostname, client.nickname, msg))
