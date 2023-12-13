"""
chanop
"""

import logging

from handle.core import Channelmode


def validate_member(client, channel, action, mode, param, CHK_TYPE):
    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if action == "+" and (channel.client_has_membermodes(client, "oaq") or not client.local):
            return 1
        elif action == "-":
            # Always allow unset.
            return 1
        return 0
    return 0


def init(module):
    Cmode_o = Channelmode()
    Cmode_o.flag = 'o'
    Cmode_o.prefix = '@'
    Cmode_o.sjoin_prefix = '@'
    Cmode_o.paramcount = 1
    Cmode_o.unset_with_param = 1
    Cmode_o.type = Channelmode.MEMBER
    Cmode_o.rank = 200  # Used to determine the position in PREFIX Isupport
    Cmode_o.level = 3
    Cmode_o.is_ok = validate_member
    Cmode_o.desc = "Give/take operator status"
    Channelmode.add(module, Cmode_o)
