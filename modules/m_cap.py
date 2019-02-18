#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/cap command
"""

import ircd

### @time=2011-10-19T16:40:51.620Z
@ircd.Modules.params(1)
@ircd.Modules.commands('cap')
def cap(self, localServer, recv):
    if recv[1].lower() in ['ls', 'list']:
        self.sends_cap = True
        caps = []
        for c in localServer.caps:
            caps.append(c)
        self._send(':{} CAP {} LS :{}'.format(localServer.hostname, self.nickname, ' '.join(caps)))

    elif recv[1].lower() == 'req':
        self.sends_cap = True
        cap = recv[2][1:].lower() if recv[2].startswith(':') else recv[2].lower()
        if cap.lower() in localServer.caps and cap not in self.caplist:
            self.caplist.append(cap)
            self._send(':{} CAP {} ACK :{}'.format(localServer.hostname, self.nickname, cap))
    elif recv[1].lower() == 'end':
        self.cap_end = True
        if not self.registered and self.nickname != '*' and self.ident:
            self.welcome()
    else:
        self.sendraw(410, '{} :Unknown CAP command'.format(recv[1]))
        #pass
