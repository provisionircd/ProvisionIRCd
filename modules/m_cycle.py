#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/cycle command
"""

import ircd

@ircd.Modules.params(1)
@ircd.Modules.commands('cycle')
def cycle(self, localServer, recv):
    for chan in recv[1].split(','):
        channel = list(filter(lambda c: c.name.lower() == chan.lower(), self.channels))
        if not channel:
            self.sendraw(442, '{} :You\'re not on that channel'.format(chan))
            continue

        channel = channel[0]
        p = {'reason': 'Cycling'}
        self.handle('PART', channel.name, params=p)
        self.handle('JOIN', '{}'.format(channel.name))
