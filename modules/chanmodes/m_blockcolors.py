#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides chmode +c (block colors)
"""

import ircd
import re

chmode = 'c'

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 no param.
@ircd.Modules.channel_modes(chmode, 3, 3, 'Blocks messages containing colors') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.hooks.pre_chanmsg()
def blockcolors_c(self, localServer, channel, msg):
    match = re.search("\x03(?:\d{1,2}(?:,\d{1,2})?)?", msg)
    if match and chmode in channel.modes:
        self.sendraw(404, '{} :Colors are blocked on this channel.'.format(channel.name))
        return 0
    return msg
