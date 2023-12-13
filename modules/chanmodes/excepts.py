"""
provides chmode +e (except list)
"""

from handle.core import Numeric, Channelmode, Hook

HEADER = {
    "name": "channelexcepts"
}


def excecptlist_is_ok(client, channel, action, param):
    return param


def display_exceptlist(client, channel, mode):
    if mode == "e":
        if channel.client_has_membermodes(client, "hoaq") or client.has_permission("channel:see:banlist"):
            for entry in reversed(channel.List[mode]):
                client.sendnumeric(Numeric.RPL_EXLIST, channel.name, entry.mask, entry.set_by, entry.set_time)
        client.sendnumeric(Numeric.RPL_ENDOFEXLIST, channel.name)
        return 1


def init(module):
    Hook.add(Hook.CHAN_LIST_ENTRY, display_exceptlist)
    Chmode_e = Channelmode()
    Chmode_e.flag = 'e'
    Chmode_e.sjoin_prefix = '"'
    Chmode_e.paramcount = 1
    Chmode_e.unset_with_param = 1
    Chmode_e.is_ok = excecptlist_is_ok
    Chmode_e.type = Channelmode.LISTMODE
    Chmode_e.param_help = '<nick!ident@host>'
    Chmode_e.desc = 'Exempts the mask from being banned'
    Channelmode.add(module, Chmode_e)
