"""
channel mode +Q
"""

# Not sure why I never implemented this?

from handle.core import Channelmode


def init(module):
    Cmode_Q = Channelmode()
    Cmode_Q.flag = 'Q'
    Cmode_Q.is_ok = Channelmode.allow_chanop
    Cmode_Q.desc = "Only channel owners can /KICK users from channel"
    Channelmode.add(module, Cmode_Q)
