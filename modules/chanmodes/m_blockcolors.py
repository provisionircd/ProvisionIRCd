#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides chmode +c (block colors)
"""

import ircd
import re

### We need to modify a variable in this module.
import modules.m_msg as privmsg

chmode = 'c'

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 no param.
@ircd.Modules.channel_modes(chmode, 3, 3, 'Blocks messages containing colors') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.events('privmsg')
def blockcolors_c(self, localServer, target, msg, module):
    if type(target).__name__ != 'Channel' or chmode not in target.modes or self.chlevel(target) >= 4 or 'o' in self.modes:
        return True
    match = re.search("\x03(?:\d{1,2}(?:,\d{1,2})?)?", msg)
    if match:
        self.sendraw(404, '{} :Colors are blocked on this channel.'.format(target.name))
        return False
    return True