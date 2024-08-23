"""
chanadmin mode (+a)
"""

from handle.core import IRCD, Channelmode


def validate_member(client, channel, action, mode, param, CHK_TYPE):
    param_client = IRCD.find_client(param)
    if CHK_TYPE == Channelmode.CHK_ACCESS:
        if channel.client_has_membermodes(client, 'q') or not client.local:
            return 1
        if action == '-' and param_client == client:
            # Always allow unset on self.
            return 1
        return 0
    return 0


def init(module):
    Cmode_a = Channelmode()
    Cmode_a.flag = 'a'
    Cmode_a.prefix = '&'
    Cmode_a.sjoin_prefix = '~'
    Cmode_a.paramcount = 1
    Cmode_a.unset_with_param = 1
    Cmode_a.type = Channelmode.MEMBER
    Cmode_a.rank = 300  # Used to determine the position in PREFIX Isupport
    Cmode_a.level = 5
    Cmode_a.is_ok = validate_member
    Cmode_a.desc = "Give/take channel admin status"
    Channelmode.add(module, Cmode_a)
