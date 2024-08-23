"""
channel mode +t
"""

from handle.core import Channelmode


def init(module):
    Chmode_t = Channelmode()
    Chmode_t.flag = 't'
    Chmode_t.paramcount = 0
    Chmode_t.is_ok = Channelmode.allow_halfop
    Chmode_t.desc = "Topic cannot be changed from outside"
    Channelmode.add(module, Chmode_t)
