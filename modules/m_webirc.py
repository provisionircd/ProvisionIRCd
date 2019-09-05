"""
webirc support
"""

import ircd

password = "eenpassword"

@ircd.Modules.commands('webirc')
def process_webirc(self, localServer, recv):
    print(recv)
    # 3 = host
    # 4 = ip
    if self.registered:
        return
    if recv[1] == password:
        print('password accepted, assigning values')
        self.hostname = recv[3] if 'dontresolve' not in self.server.conf['settings'] or ('dontresolve' in self.server.conf['settings'] and not self.server.conf['settings']['dontresolve']) else recv[4]
        self.ip = recv[4]
