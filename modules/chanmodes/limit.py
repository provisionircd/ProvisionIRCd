"""
channel mode +l
"""

import logging

from handle.core import Channelmode, Numeric, Hook


def validate_limit(client, channel, action, mode, param, CHK_TYPE):
    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if channel.client_has_membermodes(client, "oaq"):
            return 1
        return 0

    if CHK_TYPE == Channelmode.CHK_PARAM:
        if param.startswith("-"):
            param = param[1:]
        if not param.isdigit():
            return 0
        return 1

    if (action == "+" and param.isdigit()) or (action == '-'):
        return 1
    return 0


def conv_param_limit(param):
    param = int(param)
    if param > 9999:
        param = 9999
    if param < 0:
        param = 1
    return param


def sjoin_check_limit(ourlimit, theirlimit):
    if ourlimit == theirlimit:
        # Same.
        return 0

    if ourlimit > theirlimit:
        return 1
    return -1


def limit_can_join(client, channel, key):
    if client.has_permission("override:channel:join:limit"):
        return 0

    if limit_param := channel.get_param('l'):
        if channel.membercount >= int(limit_param):
            return Numeric.ERR_CHANNELISFULL
    return 0


def init(module):
    Cmode_l = Channelmode()
    Cmode_l.flag = "l"
    Cmode_l.paramcount = 1
    Cmode_l.is_ok = validate_limit
    Cmode_l.conv_param = conv_param_limit
    Cmode_l.sjoin_check = sjoin_check_limit
    Cmode_l.level = 3
    Cmode_l.param_help = "<limit> (number)"
    Cmode_l.desc = "Limits the channel users to <limit> users"
    Hook.add(Hook.CAN_JOIN, limit_can_join)
    Channelmode.add(module, Cmode_l)
