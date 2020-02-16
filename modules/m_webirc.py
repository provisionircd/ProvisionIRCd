
"""
webirc support
"""

import ircd

password = "somePassword"

@ircd.Modules.commands('webirc')
def process_webirc(self, localServer, recv):
    if self.registered:
        return
    if recv[1] == password:
        self.hostname = recv[3] if 'dontresolve' not in self.server.conf['settings'] or ('dontresolve' in self.server.conf['settings'] and not self.server.conf['settings']['dontresolve']) else recv[4]
        self.ip = recv[4]



'''
"""
webirc support
"""

import ircd

password = "somePassword"


@ircd.Modules.command
class Webirc(ircd.Command):
    def __init__(self):
        self.command = 'webirc'
        self.params = 4

    def execute(self, client, recv):
        if client.registered:
            return
        if recv[1] == password:
            client.hostname = recv[3] if 'dontresolve' not in self.ircd.conf['settings'] or ('dontresolve' in self.ircd.conf['settings'] and not self.ircd.conf['settings']['dontresolve']) else recv[4]
            client.ip = recv[4]

'''
