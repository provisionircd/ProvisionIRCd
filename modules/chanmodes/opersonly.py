"""
channel mode +O (opers-only channel)
"""

from handle.core import Numeric, Channelmode, Hook


def chmode_O_join(client, channel, key):
    if 'O' in channel.modes and 'o' not in client.user.modes:
        return Numeric.ERR_OPERONLY
    return 0


def init(module):
    Cmode_O = Channelmode()
    Cmode_O.flag = 'O'
    Cmode_O.is_ok = Channelmode.allow_opers
    Cmode_O.desc = "Only IRC Operators can join the channel"
    Channelmode.add(module, Cmode_O)
    Hook.add(Hook.CAN_JOIN, chmode_O_join)
