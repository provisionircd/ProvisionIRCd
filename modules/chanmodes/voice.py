"""
voice mode (+v)
"""

from handle.core import IRCD, Channelmode


def validate_member(client, channel, action, mode, param, CHK_TYPE):
    param_client = IRCD.find_client(param)
    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if channel.client_has_membermodes(client, "hoaq") or not client.local:
            return 1
        if action == '-' and param_client == client:
            # Always allow unset on self.
            return 1
        return 0
    return 0


def init(module):
    Cmode_v = Channelmode()
    Cmode_v.flag = 'v'
    Cmode_v.prefix = '+'
    Cmode_v.sjoin_prefix = '+'
    Cmode_v.paramcount = 1
    Cmode_v.unset_with_param = 1
    Cmode_v.type = Channelmode.MEMBER
    Cmode_v.rank = 1  # Used to determine the position in PREFIX Isupport
    Cmode_v.is_ok = validate_member
    Cmode_v.desc = "Give/take channel voice status"
    Channelmode.add(module, Cmode_v)
