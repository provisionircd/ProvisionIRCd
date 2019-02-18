#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides chmode +S (strip messages)
"""

import ircd
import re

### We need to modify a variable in this module.
import modules.m_msg as privmsg

chmode = 'S'

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes(chmode, 3, 5, 'Strip colors from messages') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.events('privmsg')
def stripmsg_S(self, localServer, target, msg, module):
    if type(target).__name__ != 'Channel' or chmode not in target.modes:
        return True
    regex = re.compile("\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)
    privmsg.msg = regex.sub('', privmsg.msg)

    ### Returning True, indicating the message is not blocked.
    return True
