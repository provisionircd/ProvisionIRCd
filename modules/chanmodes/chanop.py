"""
chanop mode (+o)
"""

from handle.core import IRCD, Channelmode


def validate_member(client, channel, action, mode, param, CHK_TYPE):
    param_client = IRCD.find_client(param)
    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if channel.client_has_membermodes(client, "oaq") or not client.local:
            return 1
        if action == '-' and param_client == client:
            # Always allow unset on self.
            return 1
        return 0
    return 0


def init(module):
    Cmode_o = Channelmode()
    Cmode_o.flag = 'o'
    Cmode_o.prefix = '@'
    Cmode_o.sjoin_prefix = '@'
    Cmode_o.paramcount = 1
    Cmode_o.unset_with_param = 1
    Cmode_o.type = Channelmode.MEMBER
    Cmode_o.rank = 200  # Used to determine the position in PREFIX Isupport
    Cmode_o.level = 3
    Cmode_o.is_ok = validate_member
    Cmode_o.desc = "Give/take operator status"
    Channelmode.add(module, Cmode_o)
