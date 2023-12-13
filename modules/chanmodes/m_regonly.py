"""
provides chmode +R (strip messages)
"""

from handle.core import Channelmode, Numeric, Hook


def reg_only_join(client, channel, key):
    if 'R' in channel.modes and 'r' not in client.user.modes:
        return Numeric.ERR_NEEDREGGEDNICK
    return 0


def init(module):
    Hook.add(Hook.CAN_JOIN, reg_only_join)
    Chmode_R = Channelmode()
    Chmode_R.flag = 'R'
    Chmode_R.desc = "Only registered users may join"
    Channelmode.add(module, Chmode_R)
