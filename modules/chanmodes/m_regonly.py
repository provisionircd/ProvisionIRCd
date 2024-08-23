"""
provides chmode +R (only registered users can join)
and +M (only registered or voiced users can speak)
"""

from handle.core import Channelmode, Numeric, Hook


def reg_only_join(client, channel, key):
    if 'R' in channel.modes and 'r' not in client.user.modes and not client.has_permission("channel:override:join:regonly"):
        return Numeric.ERR_NEEDREGGEDNICK
    return 0


def reg_only_msg(client, channel, message, sendtype):
    if 'M' not in channel.modes:
        return Hook.ALLOW

    if 'r' in client.user.modes or channel.client_has_membermodes(client, "vhoaq") or client.has_permission("channel:override:message:regonly"):
        return Hook.ALLOW

    client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "You need a registered nickname to speak in this channel")
    return Hook.DENY


def init(module):
    Chmode_R = Channelmode()
    Chmode_R.flag = 'R'
    Chmode_R.is_ok = Channelmode.allow_chanop
    Chmode_R.desc = "Only registered users may join"
    Channelmode.add(module, Chmode_R)
    Chmode_M = Channelmode()
    Chmode_M.flag = 'M'
    Chmode_M.is_ok = Channelmode.allow_chanop
    Chmode_M.desc = "Only registered or voiced users may speak"
    Channelmode.add(module, Chmode_M)
    Hook.add(Hook.CAN_JOIN, reg_only_join)
    Hook.add(Hook.CAN_SEND_TO_CHANNEL, reg_only_msg)
