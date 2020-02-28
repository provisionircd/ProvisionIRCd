"""
provides chmode +S (strip messages)
"""

import ircd
import re

class Chmode_S(ircd.ChannelMode):
    def __init__(self):
        self.mode = 'S'
        self.desc = 'Strip colors from messages'
        self.type = 3


@ircd.Modules.hooks.pre_chanmsg()
def stripmsg_S(self, localServer, channel, msg):
    if 'S' in channel.modes:
        regex = re.compile("\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)
        msg = regex.sub('', msg)
        return msg
