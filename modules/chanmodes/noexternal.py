"""
channel mode +n
"""

from handle.core import Channelmode


def init(module):
    Cmode_n = Channelmode()
    Cmode_n.flag = 'n'
    Cmode_n.is_ok = Channelmode.allow_halfop
    Cmode_n.desc = "No external messages allowed"
    Channelmode.add(module, Cmode_n)
