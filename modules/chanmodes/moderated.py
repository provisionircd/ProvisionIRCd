"""
channel mode +m (moderated, only +v or higher can speak)
"""

from handle.core import Channelmode, Hook, Numeric
from modules.m_msg import add_oper_override


def moderated_msg_check(client, channel, msg, sendtype):
    if 'm' in channel.modes and not channel.client_has_membermodes(client, "vhoaq"):
        if not client.has_permission("channel:override:message:moderated"):
            client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "Cannot send to channel (+m)")
            return Hook.DENY
        add_oper_override('m')
    return Hook.CONTINUE


def init(module):
    Cmode_m = Channelmode()
    Cmode_m.flag = 'm'
    Cmode_m.paramcount = 0
    Cmode_m.is_ok = Channelmode.allow_halfop
    Cmode_m.desc = "Users need voice (+v) or higher to speak"
    Channelmode.add(module, Cmode_m)
    Hook.add(Hook.CAN_SEND_TO_CHANNEL, moderated_msg_check)
