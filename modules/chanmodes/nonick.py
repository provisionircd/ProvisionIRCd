"""
channel mode +N (nick changes are not allowed)
"""

from handle.core import Channelmode, Hook, Numeric


def can_change_nick(client, newnick):
    if client.has_permission("channel:override:no-nick"):
        return Hook.ALLOW
    for channel in client.channels:
        if 'N' in channel.modes and not channel.client_has_membermodes(client, 'q'):
            # Channel owners can bypass channel mode +N.
            # Client needs channel owner (or channel:override:no-nick oper permission) on all channels it's in
            # if that channel has +N.
            client.sendnumeric(Numeric.ERR_NONICKCHANGE, channel.name)
            return Hook.DENY
    return Hook.ALLOW


def init(module):
    Cmode_N = Channelmode()
    Cmode_N.flag = 'N'
    Cmode_N.is_ok = Channelmode.allow_chanop
    Cmode_N.desc = "Nick changes are not allowed in the channel"
    Channelmode.add(module, Cmode_N)
    Hook.add(Hook.PRE_LOCAL_NICKCHANGE, can_change_nick)
