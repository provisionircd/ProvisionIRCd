"""
channel mode +k
"""

from handle.core import Numeric, Channelmode, Hook


def key_is_ok(client, channel, action, mode, param, CHK_TYPE):
    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if channel.client_has_membermodes(client, "oaq"):
            return 1
        return 0

    if CHK_TYPE == Channelmode.CHK_PARAM:
        for char in param:
            if not char.isalpha() and not char.isdigit():
                client.sendnumeric(Numeric.ERR_INVALIDMODEPARAM, channel.name, 'k', '*', f"Key contains invalid character: {char}")
                return 0
        return 1
    return 0


def can_join_key(client, channel, key):
    if client.has_permission("channel:override:join:key"):
        return 0
    if 'k' in channel.modes and key != channel.get_param('k'):
        return Numeric.ERR_BADCHANNELKEY
    return 0


def key_conv_param(param):
    return param[:12]


def sjoin_check_key(ourkey, theirkey):
    if ourkey == theirkey:
        # Same.
        return 0

    our_score = 0
    their_score = 0
    for char in ourkey:
        our_score += ord(char)
    for char in theirkey:
        their_score += ord(char)

    if our_score > their_score:
        return 1

    return -1


def init(module):
    Cmode_k = Channelmode()
    Cmode_k.flag = "k"
    Cmode_k.paramcount = 1
    Cmode_k.unset_with_param = 1
    Cmode_k.is_ok = key_is_ok
    Cmode_k.conv_param = key_conv_param
    Cmode_k.sjoin_check = sjoin_check_key
    Cmode_k.param_help = "<key>"
    Cmode_k.desc = "Channel requires a key to join"
    Cmode_k.level = 3
    Channelmode.add(module, Cmode_k)
    Hook.add(Hook.CAN_JOIN, can_join_key)
