"""
channel mode +u (auditorium)
"""

from handle.core import Channelmode, Hook


def can_see_member(client, target, channel):
    if 'u' in channel.modes:
        if client in channel.clients() and (target in channel.seen_dict[client] or client.has_permission("channel:see:names") or client == target):
            return Hook.CONTINUE
        if not channel.client_has_membermodes(target, "hoaq") and not channel.client_has_membermodes(client, "oaq"):
            return Hook.DENY

    return Hook.CONTINUE


def init(module):
    Cmode_u = Channelmode()
    Cmode_u.flag = 'u'
    Cmode_u.is_ok = Channelmode.allow_chanowner
    Cmode_u.desc = "Only +h or higher are visible on the channel"
    Channelmode.add(module, Cmode_u)
    Hook.add(Hook.VISIBLE_ON_CHANNEL, can_see_member)
