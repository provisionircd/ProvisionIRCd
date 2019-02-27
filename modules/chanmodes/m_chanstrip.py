#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides chmode +S (strip messages)
"""

import ircd
import re
import os
import sys

chmode = 'S'

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes(chmode, 3, 2, 'Strip colors from messages') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.hooks.pre_chanmsg()
def stripmsg_S(self, localServer, channel, msg):
    if chmode not in channel.modes:
        return msg
    regex = re.compile("\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)
    msg = regex.sub('', msg)
    return msg
