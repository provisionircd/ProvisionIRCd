"""
channel mode +n (no external messages)
"""

from handle.core import Channelmode


def init(module):
    Cmode_n = Channelmode()
    Cmode_n.flag = 'n'
    Cmode_n.desc = "No external messages allowed"
    Channelmode.add(module, Cmode_n)
