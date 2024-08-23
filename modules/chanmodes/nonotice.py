"""
channel mode +T (no notices in the channel)
"""

from handle.core import Channelmode, Hook, Numeric


def can_channel_notice(client, channel, message, sendtype):
    if 'T' not in channel.modes or sendtype != "NOTICE":
        return Hook.ALLOW

    if not client.user or channel.client_has_membermodes(client, "q") or client.has_permission("channel:override:message:notice"):
        return Hook.ALLOW

    client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "Notices are not permitted in this channel")
    return Hook.DENY


def init(module):
    Cmode_T = Channelmode()
    Cmode_T.flag = 'T'
    Cmode_T.desc = "Notices are not allowed in the channel"
    Channelmode.add(module, Cmode_T)
    Hook.add(Hook.CAN_SEND_TO_CHANNEL, can_channel_notice)
