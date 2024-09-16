"""
channel mode +Q (only +q can /KICK)
"""

from handle.core import Channelmode, Hook, Numeric


def chmode_Q_can_kick(client, target_client, channel, reason, oper_override):
    if 'Q' in channel.modes and channel.level(client) < 5 and not client.has_permission("channel:override:kick:no-kick"):
        client.sendnumeric(Numeric.ERR_CANNOTDOCOMMAND, channel.name, "KICKs are not permitted in this channel")
        return Hook.DENY

    elif 'Q' in channel.modes and not channel.client_has_membermodes(client, 'q'):
        oper_override[0] = 1
    return Hook.CONTINUE


def init(module):
    Cmode_Q = Channelmode()
    Cmode_Q.flag = 'Q'
    Cmode_Q.is_ok = Channelmode.allow_chanop
    Cmode_Q.desc = "Only channel owners can /KICK users from channel"
    Channelmode.add(module, Cmode_Q)
    Hook.add(Hook.CAN_KICK, chmode_Q_can_kick)
