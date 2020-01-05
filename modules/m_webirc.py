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
