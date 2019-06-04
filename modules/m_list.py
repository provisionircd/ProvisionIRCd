"""
/list command
"""

import ircd
import time

@ircd.Modules.support('SAFELIST')
@ircd.Modules.support('ELIST=U')
@ircd.Modules.commands('list')
def list(self, localServer, recv):
    self.flood_safe = True
    self.sendraw(321, 'Channel :Users  Name')
    minusers, maxusers = None, None
    if len(recv) >= 2 and recv[1][0] in '<>' and len(recv[1]) > 1 and recv[1][1].isdigit():
        usercount = recv[1].split(',')
        for c in [c for c in usercount if len(c) > 1]:
            if c[0] == '<':
                maxusers = c[1:]
            elif c[0] == '>':
                minusers = c[1:]
    for channel in localServer.channels:
        if maxusers is not None and len(channel.users) > int(maxusers):
            continue
        if minusers is not None and len(channel.users) < int(minusers):
            continue
        if ('s' in channel.modes or 'p' in channel.modes) and (self not in channel.users and 'o' not in self.modes):
            if 'p' in channel.modes:
                self.sendraw(322, '* {} :'.format(len(channel.users)))
            continue
        else:
            self.sendraw(322, '{} {} :[+{}] {}'.format(channel.name, len(channel.users), channel.modes, channel.topic))
    self.sendraw(323, ':End of /LIST')
