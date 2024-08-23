"""
halfop mode (+h)
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
    Cmode_h = Channelmode()
    Cmode_h.flag = 'h'
    Cmode_h.prefix = '%'
    Cmode_h.sjoin_prefix = '%'
    Cmode_h.paramcount = 1
    Cmode_h.unset_with_param = 1
    Cmode_h.type = Channelmode.MEMBER
    Cmode_h.rank = 100  # Used to determine the position in PREFIX Isupport
    Cmode_h.level = 3
    Cmode_h.is_ok = validate_member
    Cmode_h.desc = "Give/take channel halfop status"
    Channelmode.add(module, Cmode_h)
