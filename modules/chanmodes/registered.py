"""
channel mode +r (registered channel)
"""

from handle.core import Channelmode


def init(module):
    Cmode_r = Channelmode()
    Cmode_r.flag = 'r'
    Cmode_r.is_ok = Channelmode.allow_none
    Cmode_r.desc = "Channel is registered"
    Channelmode.add(module, Cmode_r)
