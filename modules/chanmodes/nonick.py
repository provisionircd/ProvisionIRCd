"""
channel mode +N
"""

from handle.core import Channelmode


def init(module):
    Cmode_N = Channelmode()
    Cmode_N.flag = 'N'
    Cmode_N.is_ok = Channelmode.allow_chanowner
    Cmode_N.desc = "Nick changes are not allowed in the channel"
    Channelmode.add(module, Cmode_N)
