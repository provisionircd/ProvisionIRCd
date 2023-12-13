"""
certfp bans/exceptions/invex
+b/e/I ~certfp:<fingerprint>
"""

import re

from handle.core import Extban
from handle.logger import logging


def certfp_is_valid(client, channel, action, mode, param):
    if len(param.split(':')) < 2:
        return 0
    cert = param.split(':')[-1]
    pattern = r"[A-Fa-f0-9]{64}$"
    if not re.match(pattern, cert):
        return 0

    return param


def certfp_is_match(client, channel, mask):
    """
    mask == raw ban entry from a channel.
    Called by channel.is_banned(), channel.is_exempt() or channel.is_invex()
    """

    fp_ban = mask.split(':')[-1]
    if not client.local.tls:
        return 0
    if (client_fp := client.get_md_value("certfp")) and client_fp.lower() == fp_ban.lower():
        return 1


class CertFp:
    name = "certfp"
    flag = "S"
    paramcount = 1

    # Checks if the param is valid, in which case it returns it.
    is_ok = certfp_is_valid

    # Called by Channel.is_banned() and takes the client, channel, and the mask.
    is_match = certfp_is_match


def init(module):
    Extban.add(CertFp)
