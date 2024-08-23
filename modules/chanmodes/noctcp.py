"""
channel mode +C (no CTCP in the channel)
"""

from handle.core import Channelmode, Hook, Numeric


def msg_ctcp(client, channel, message, sendtype):
    if 'C' not in channel.modes:
        return Hook.ALLOW

    if channel.client_has_membermodes(client, "aq") or client.has_permission("channel:override:message:ctcp"):
        return Hook.ALLOW

    if message[0] == '' and message[-1] == '':
        client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "CTCPs are not permitted in this channel")
        return Hook.DENY

    return Hook.ALLOW


def init(module):
    Cmode_C = Channelmode()
    Cmode_C.flag = 'C'
    Cmode_C.desc = "CTCPs are not allowed in the channel"
    Channelmode.add(module, Cmode_C)
    Hook.add(Hook.CAN_SEND_TO_CHANNEL, msg_ctcp)
