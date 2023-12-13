"""
timed bans, +b/e/I ~timed:<min>:<mask>
"""

import time

from handle.core import IRCD, Extban, Hook, Command
from handle.functions import make_mask
from handle.logger import logging

HEADER = {
    "name": "extbans/timedbans"
}


def check_expired_bans():
    def send_mode_lines(modes):
        Command.do(IRCD.me, "MODE", chan.name, f"-{modes}", *bans, '0')

    for chan in IRCD.get_channels():
        modes = ''
        bans = []
        for listmode in chan.List:
            for entry in list(chan.List[listmode]):
                mask_split = entry.mask.split(':')
                if mask_split[0][0] != Extban.symbol or mask_split[0][1:] not in [TimedBans.flag, TimedBans.name]:
                    continue
                if not mask_split[1].isdigit():
                    continue
                duration = int(mask_split[1])
                if int(time.time()) >= entry.set_time + (duration * 60):
                    modes += listmode
                    bans.append(entry.mask)
                    if len(bans) >= 12:
                        send_mode_lines(modes)
                        bans = []
                        modes = ''
        if bans:
            send_mode_lines(modes)


def timedban_is_valid(client, channel, action, mode, param):
    param_split = param.split(':')
    if len(param_split) < 3 or len(param_split) > 40:
        return 0
    b_time = param_split[1]
    if not b_time.isdigit():
        return 0
    if len(param_split) > 3:
        extra = param_split[2:][-2]
        logging.debug(f"Extra: {extra}")
        logging.debug(f"Param split: {param_split}")
        extra = param_split[2]
        if not extra.startswith(Extban.symbol):
            return 0
        # (client, channel, action, mode, param):
        if not (ext := next((e for e in Extban.table if extra in [Extban.symbol + e.name, Extban.symbol + e.flag]), 0)):
            return 0
        ext_param = Extban.symbol + ext.name + ':' + param_split[-1]
        ext_param = Extban.symbol + ext.name + ':' + ':'.join(param_split[3:])
        logging.debug(f"Ext param: {ext_param}")
        if ext.is_ok(client, channel, action, mode, ext_param):
            param = Extban.convert_param(param, convert_to_name=1)
            return param
    banmask = make_mask(param_split[-1])
    param = f'{":".join(param_split[:-1])}:{banmask}'
    return param


def timedban_is_match(client, channel, mask):
    """
    mask == raw ban entry from a channel.
    Called by channel.is_banned(), channel.is_exempt() or channel.is_invex()
    """
    mask_split = mask.split(':')
    if len(mask_split) < 3:
        return 0
    mask = mask.split(':')[-1]
    if len(mask_split) > 3:
        extra = mask_split[2]
        if extra := next((e for e in Extban.table if extra in Extban.symbol + e.name == extra), 0):
            if extra.is_match(client, channel, mask):
                return 1
    return IRCD.client_match_mask(client, mask)


class TimedBans:
    name = "timed"
    flag = "t"
    paramcount = 1
    is_ok = timedban_is_valid
    is_match = timedban_is_match


def init(module):
    Hook.add(Hook.LOOP, check_expired_bans)
    Extban.add(TimedBans)
