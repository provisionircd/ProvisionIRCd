"""
provides chmode +w (white list)
"""

from handle.core import Numeric, Channelmode, Hook

HEADER = {
    "name": "channelbans"
}


def banlist_is_ok(client, channel, action, param):
    return param


def display_banlist(client, channel, mode):
    if mode == "b":
        if channel.client_has_membermodes(client, "hoaq") or client.has_permission("channel:see:banlist"):
            for entry in reversed(channel.List[mode]):
                client.sendnumeric(Numeric.RPL_BANLIST, channel.name, entry.mask, entry.set_by, entry.set_time)
        client.sendnumeric(Numeric.RPL_ENDOFBANLIST, channel.name)
        return 1


def ban_can_join(client, channel, key):
    if (channel.is_banned(client) and not channel.is_exempt(client)) and not client.has_permission("override:channel:join:ban"):
        return Numeric.ERR_BANNEDFROMCHAN
    return 0


def init(module):
    Hook.add(Hook.CHAN_LIST_ENTRY, display_banlist)
    Hook.add(Hook.CAN_JOIN, ban_can_join)
    Chmode_b = Channelmode()
    Chmode_b.flag = 'b'
    Chmode_b.sjoin_prefix = '&'
    Chmode_b.paramcount = 1
    Chmode_b.unset_with_param = 1
    Chmode_b.is_ok = banlist_is_ok
    Chmode_b.type = Channelmode.LISTMODE
    Chmode_b.param_help = '<nick!ident@host>'
    Chmode_b.desc = 'Bans the given hostmask from joining the channel'
    Channelmode.add(module, Chmode_b)
