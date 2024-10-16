"""
channel mode +n (no external messages)
"""

from handle.core import Channelmode, Hook, Numeric
from modules.m_msg import add_oper_override


def noexternal_msg_check(client, channel, msg, sendtype):
    if 'n' in channel.modes and not channel.find_member(client):
        if not client.has_permission("channel:override:message:outside"):
            client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "No external messages")
            return Hook.DENY
        add_oper_override('n')
    return Hook.CONTINUE


def init(module):
    Cmode_n = Channelmode()
    Cmode_n.flag = 'n'
    Cmode_n.desc = "No external messages allowed"
    Channelmode.add(module, Cmode_n)
    Hook.add(Hook.CAN_SEND_TO_CHANNEL, noexternal_msg_check)
