"""
provides chmode +I (invex list)
"""

from handle.core import Channelmode, Isupport, Numeric, Hook

HEADER = {
    "name": "channelinvex"
}


def invexlist_is_ok(client, channel, action, param):
    return param


def display_invexlist(client, channel, mode):
    if mode == "I":
        if channel.client_has_membermodes(client, "hoaq") or client.has_permission("channel:see:banlist"):
            for entry in reversed(channel.List[mode]):
                client.sendnumeric(Numeric.RPL_INVEXLIST, channel.name, entry.mask, entry.set_by, entry.set_time)
        client.sendnumeric(Numeric.RPL_ENDOFINVEXLIST, channel.name)
        return 1


def init(module):
    Hook.add(Hook.CHAN_LIST_ENTRY, display_invexlist)
    Chmode_I = Channelmode()
    Chmode_I.flag = 'I'
    Chmode_I.sjoin_prefix = "'"
    Chmode_I.paramcount = 1
    Chmode_I.unset_with_param = 1
    Chmode_I.is_ok = invexlist_is_ok
    Chmode_I.type = Channelmode.LISTMODE
    Chmode_I.param_help = "<nick!ident@host>"
    Chmode_I.desc = "Hosts matching an invex can bypass +i"
    Channelmode.add(module, Chmode_I)
    Isupport.add("INVEX")
