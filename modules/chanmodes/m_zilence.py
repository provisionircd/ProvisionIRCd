#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides channel-user mode +z (zilence)
"""

import ircd
import re

chmode = 'z'

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes(chmode, 4, 3, 'Users matching a \'Zilence\' cannot speak', 'user', '-', '[nickname]') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.hooks.pre_chanmsg()
def zilence_z(self, localServer, channel, msg):
    if self not in channel.usermodes or chmode not in channel.usermodes[self]:
        return msg
    self.sendraw(404, '{} :You cannot speak (+z)'.format(channel.name))
    return 0

def unload(localServer):
    localServer.chstatus = re.sub(chmode, '', localServer.chstatus)
