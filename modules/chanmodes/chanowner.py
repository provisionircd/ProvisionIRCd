"""
chanowner mode (+q)
"""

from handle.core import IRCD, Channelmode, Hook, Numeric


def list_chanowners(client, channel, mode):
    if mode == 'q' and (cmode := IRCD.get_channelmode_by_flag(mode)):
        for entry in [c for c in reversed(channel.clients()) if channel.client_has_membermodes(c, mode)]:
            client.sendnumeric(Numeric.RPL_QLIST, channel.name, entry.name)
        client.sendnumeric(Numeric.RPL_ENDOFQLIST, channel.name)
        return 1


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
    Cmode_q = Channelmode()
    Cmode_q.flag = 'q'
    Cmode_q.prefix = '~'
    Cmode_q.sjoin_prefix = '*'
    Cmode_q.paramcount = 1
    Cmode_q.unset_with_param = 1
    Cmode_q.type = Channelmode.MEMBER
    Cmode_q.rank = 400  # Used to determine the position in PREFIX Isupport
    Cmode_q.level = 5
    Cmode_q.is_ok = validate_member
    Cmode_q.desc = "Give/take channel owner status"
    Channelmode.add(module, Cmode_q)
    Hook.add(Hook.CHAN_LIST_ENTRY, list_chanowners)
