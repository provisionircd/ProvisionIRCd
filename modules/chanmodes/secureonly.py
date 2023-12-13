"""
channel mode +z (requires TLS to join the channel)
"""

from handle.core import Numeric, Channelmode, Hook


def chmode_z_is_ok(client, channel, action, mode, param, CHK_TYPE):
    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if 'z' not in client.user.modes and not client.has_permission("channel:override:mode"):
            client.sendnumeric(Numeric.ERR_INVALIDMODEPARAM, channel.name, 'z', '*', "You need to be connected with TLS to set mode +z.")
            """ Don't return 0 here, to hide ERR_CHANOPRIVSNEEDED """
            return
        return 1
    return 0


def chmode_z_only_join(client, channel, key):
    if client.has_permission("channel:override:join:secureonly"):
        return 0
    if 'z' in channel.modes and 'z' not in client.user.modes:
        return Numeric.ERR_SECUREONLY
    return 0


def init(module):
    Cmode_z = Channelmode()
    Cmode_z.flag = 'z'
    Cmode_z.is_ok = chmode_z_is_ok
    Cmode_z.desc = "Requires a TLS connection to join the channel"
    Channelmode.add(module, Cmode_z)
    Hook.add(Hook.CAN_JOIN, chmode_z_only_join)
