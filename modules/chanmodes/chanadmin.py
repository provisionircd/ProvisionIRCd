"""
chanadmin (+a)
"""

import logging

from handle.core import Channelmode


def validate_member(client, channel, action, mode, param, CHK_TYPE):

    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if action == "+" and (channel.client_has_membermodes(client, "aq") or not client.local):
            return 1
        elif action == "-":
            # Always allow unset.
            return 1
        logging.debug(f"[{client.name}] Insufficient access to set {action}{mode} on channel {channel.name}")
        return 0
    return 0


def init(module):
    Cmode_a = Channelmode()
    Cmode_a.flag = 'a'
    Cmode_a.prefix = '&'
    Cmode_a.sjoin_prefix = '~'
    Cmode_a.paramcount = 1
    Cmode_a.unset_with_param = 1
    Cmode_a.type = Channelmode.MEMBER
    Cmode_a.rank = 300  # Used to determine the position in PREFIX Isupport
    Cmode_a.level = 4
    Cmode_a.is_ok = validate_member
    Cmode_a.desc = "Give/take channel admin status"
    Channelmode.add(module, Cmode_a)
