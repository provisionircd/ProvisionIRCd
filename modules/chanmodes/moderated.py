"""
channel mode +m
"""

from handle.core import Channelmode


def init(module):
    Cmode_m = Channelmode()
    Cmode_m.flag = 'm'
    Cmode_m.paramcount = 0
    Cmode_m.is_ok = Channelmode.allow_halfop
    Cmode_m.desc = "Users need voice (+v) or higher to speak"
    Channelmode.add(module, Cmode_m)
