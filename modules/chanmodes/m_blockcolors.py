"""
provides chmode +c (block colors)
"""

import ircd
import re

chmode = 'c'

class Chmode_c(ircd.ChannelMode):
    def __init__(self):
        self.mode = chmode
        self.desc = 'Blocks messages containing colors'


@ircd.Modules.hooks.pre_chanmsg()
def blockcolors_c(self, localServer, channel, msg):
    match = re.search("\x03(?:\d{1,2}(?:,\d{1,2})?)?", msg)
    if match and chmode in channel.modes:
        self.sendraw(404, '{} :Colors are blocked on this channel.'.format(channel.name))
        return 0
