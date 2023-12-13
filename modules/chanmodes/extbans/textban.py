"""
~text extban, textban
"""

import re

from handle.core import Numeric, Extban, Hook
from handle.functions import is_match
from handle.logger import logging
from modules.chanmodes.extbans.timedbans import TimedBans


def blockmsg_is_valid(client, channel, action, mode, param):
    if mode != 'b':
        logging.debug(f"Only +b is supported for this extban")
        return 0

    pattern = r":(block|replace):([^:]+)[:]?(.*)?$"
    match = re.findall(pattern, param)
    if not match:
        logging.debug(f"Sub-param {param} does not meet the regex critera: {pattern}")
        return 0

    match = match[0]
    tb_type = match[0]
    if tb_type == "replace" and len(match) < 3:
        return 0

    return param


def check_text_block(client, channel, msg: list):
    for tb in channel.List['b']:
        mask_split = tb.mask.split(':')
        timed = 1 if mask_split[0][1:] == TimedBans.name else 0
        if mask_split[0][0] != Extban.symbol or \
                (mask_split[0][1:] not in [Textban.flag, Textban.name] and
                 # When combined with timedban, the textban name or flag gets shifted 2 places.
                 mask_split[2][1:] not in [Textban.flag, Textban.name]):
            continue
        tb_type = mask_split[1] if not timed else mask_split[3]
        tb_match = mask_split[2] if not timed else mask_split[4]
        if tb_type == "block":
            _msg = ' '.join(msg)
            if is_match(tb_match.lower(), _msg.lower()):
                client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "Cannot send to channel (+b ~text)")
                return Hook.DENY
        elif tb_type == "replace":
            tb_replace_to = mask_split[3]
            for idx, word in enumerate(msg):
                if is_match(tb_match, word):
                    msg[idx] = tb_replace_to


class Textban:
    name = "text"
    flag = "T"
    paramcount = 1
    is_ok = blockmsg_is_valid


def init(module):
    Extban.add(Textban)
    Hook.add(Hook.PRE_LOCAL_CHANMSG, check_text_block)
    Hook.add(Hook.PRE_LOCAL_CHANNOTICE, check_text_block)
