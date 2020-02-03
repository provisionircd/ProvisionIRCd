"""
/error command (server)
"""

import ircd

@ircd.Modules.command
class Error(ircd.Command):
    def __init__(self):
        self.command = 'error'
        self.params = 1
        self.req_class = 'Server'

    def execute(self, client, recv):
        msg = ' '.join(recv[2:])[1:]
        self.ircd.snotice('s', '*** {}'.format(msg), local=True)
        client.quit(msg, silent=True)
