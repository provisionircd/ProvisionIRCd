"""
provides chmode +c (block colors)
"""

import re

from handle.core import Channelmode, Numeric, Hook


def blockcolors_c(client, channel, msg, sendtype):
    if 'c' not in channel.modes:
        return 1

    if channel.client_has_membermodes(client, "oaq") or client.has_permission("channel:override:message:color"):
        return 1

    testmsg = ' '.join(msg)
    if re.search(r"\x03(?:\d{1,2}(?:,\d{1,2})?)?", testmsg):
        client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "Colors are blocked on this channel")
        return Hook.DENY

    return 1


def init(module):
    Chmode_c = Channelmode()
    Chmode_c.flag = 'c'
    Chmode_c.is_ok = Channelmode.allow_halfop
    Chmode_c.desc = "Blocks messages containing colors"
    Channelmode.add(module, Chmode_c)
    Hook.add(Hook.CAN_SEND_TO_CHANNEL, blockcolors_c)
