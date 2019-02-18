#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides channel-user mode +z (zilence)
"""

import ircd
import re

### We need to modify a variable in this module.
import modules.m_msg as privmsg

chmode = 'z'

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes(chmode, 4, 3, 'Users matching a \'Zilence\' cannot speak', 'user', '-', '[nickname]') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.events('privmsg')
def zilence_z(self, localServer, target, msg, module):
    if type(target).__name__ != 'Channel' or self not in target.usermodes or chmode not in target.usermodes[self]:
        return True
    self.sendraw(404, '{} :You cannot speak (+z)'.format(target.name))
    return False

def unload(self):
    ### Module unloaded, remove chmodes from core.
    self.chstatus = re.sub(chmode, '', self.chstatus)
    ### Remove prefix.

