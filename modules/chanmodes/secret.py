"""
channel mode +s
"""

from handle.core import Channelmode


def init(module):
    Cmode_s = Channelmode()
    Cmode_s.flag = 's'
    Cmode_s.paramcount = 0
    Cmode_s.is_ok = Channelmode.allow_chanop
    Cmode_s.desc = "Secret channel (not showing up in /list, /whois, etc.)"
    Channelmode.add(module, Cmode_s)
