"""
provides chmode +c (block colors)
"""

import re

from handle.core import Channelmode, Numeric, Hook


def blockcolors_c(client, channel, msg, sendtype):
    if 'c' not in channel.modes:
        return Hook.ALLOW

    if channel.client_has_membermodes(client, "aq") or client.has_permission("channel:override:message:color"):
        return Hook.ALLOW

    testmsg = ' '.join(msg)
    if re.search(r"\x03(?:\d{1,2}(?:,\d{1,2})?)?", testmsg):
        client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "Colors are blocked on this channel")
        return Hook.DENY

    return Hook.ALLOW


def init(module):
    Chmode_c = Channelmode()
    Chmode_c.flag = 'c'
    Chmode_c.is_ok = Channelmode.allow_chanop
    Chmode_c.desc = "Blocks messages containing colors"
    Channelmode.add(module, Chmode_c)
    Hook.add(Hook.CAN_SEND_TO_CHANNEL, blockcolors_c)
