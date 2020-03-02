
"""
webirc support
"""

import ircd

password = "somePassword"


class Webirc(ircd.Command):
    def __init__(self):
        self.command = 'webirc'


    def execute(self, client, recv):
        if client.registered:
            return
        if recv[1] == password:
            client.hostname = recv[3] if 'dontresolve' not in self.ircd.conf['settings'] or\
            ('dontresolve' in self.ircd.conf['settings'] and not self.ircd.conf['settings']['dontresolve']) else recv[4]
            client.ip = recv[4]
