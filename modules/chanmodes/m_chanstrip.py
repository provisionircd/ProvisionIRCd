"""
provides chmode +S (strip colors, bold, underline from messages)
"""

from handle.core import IRCD, Channelmode, Hook


def stripmsg_S(client, channel, msg, prefix):
    if 'S' in channel.modes:
        for idx, entry in enumerate(msg):
            msg[idx] = IRCD.strip_format(entry)


def init(module):
    Chmode_S = Channelmode()
    Chmode_S.flag = 'S'
    Chmode_S.is_ok = Channelmode.allow_chanop
    Chmode_S.desc = "Strip colors and other formatting from channel messages"
    Channelmode.add(module, Chmode_S)
    Hook.add(Hook.PRE_LOCAL_CHANMSG, stripmsg_S)
    Hook.add(Hook.PRE_LOCAL_CHANNOTICE, stripmsg_S)
