
"""
webirc support
"""

import ircd

password = "somePassword"

# TODO: limit only to specific origin hosts.


class Webirc(ircd.Command):
    def __init__(self):
        self.command = 'webirc'

    def execute(self, client, recv):
        if client.registered or recv[1] != password:
            return
        client.hostname = recv[3] if 'dontresolve' not in self.ircd.conf['settings'] or\
        ('dontresolve' in self.ircd.conf['settings'] and not self.ircd.conf['settings']['dontresolve']) else recv[4]
        client.ip = recv[4]
