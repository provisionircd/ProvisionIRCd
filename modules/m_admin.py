"""
/admin command
"""

import ircd


@ircd.Modules.command
class Admin(ircd.Command):
    def __init__(self):
        self.command = 'admin'

    def execute(self, client, recv):
        client.sendraw(256, ':Administrative info about {}'.format(self.ircd.hostname))
        for line in self.ircd.conf['admin']:
            client.sendraw(257, ':{}'.format(line))
