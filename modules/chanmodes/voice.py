"""
voice
"""

import logging

from handle.core import Channelmode


def validate_member(client, channel, action, mode, param, CHK_TYPE):
    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if action == "+" and (channel.client_has_membermodes(client, "hoaq") or not client.local):
            return 1
        elif action == "-":
            # Always allow unset.
            return 1
        return 0

    return 0


def init(module):
    Cmode_v = Channelmode()
    Cmode_v.flag = 'v'
    Cmode_v.prefix = '+'
    Cmode_v.sjoin_prefix = '+'
    Cmode_v.paramcount = 1
    Cmode_v.unset_with_param = 1
    Cmode_v.type = Channelmode.MEMBER
    Cmode_v.rank = 1  # Used to determine the position in PREFIX Isupport
    Cmode_v.is_ok = validate_member
    Cmode_v.desc = "Give/take channel voice status"
    Channelmode.add(module, Cmode_v)
