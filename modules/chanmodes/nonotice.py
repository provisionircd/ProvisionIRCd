"""
channel mode +T (no notices in the channel)
"""

from handle.core import Channelmode, Hook, Numeric


def can_channel_notice(client, channel, message, sendtype):
    if 'T' not in channel.modes or sendtype != "NOTICE":
        return 1

    if not client.user or channel.client_has_membermodes(client, "aq") or client.has_permission("channel:override:message:notice"):
        return 1

    client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "Notices are not permitted in this channel")
    return 0


def init(module):
    Cmode_T = Channelmode()
    Cmode_T.flag = 'T'
    Cmode_T.is_ok = Channelmode.allow_halfop
    Cmode_T.desc = "Notices are not allowed in the channel"
    Channelmode.add(module, Cmode_T)
    Hook.add(Hook.CAN_SEND_TO_CHANNEL, can_channel_notice)
