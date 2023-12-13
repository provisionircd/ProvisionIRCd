"""
account bans/exceptions/invex
+b/e/I ~account:accountname
"""

import re

from handle.core import Extban, Isupport
from handle.logger import logging


def account_is_valid(client, channel, action, mode, param):
    if len(param.split(':')) != 2:
        return 0
    account = param.split(':')[1]
    if ('*' in account or '0' in account) and len(account) < 2:
        return 0
    return param


def account_is_match(client, channel, mask):
    """
    mask == raw ban entry from a channel.
    Called by channel.is_banned(), channel.is_exempt() or channel.is_invex()
    """

    account_match = mask.split(':')[-1]
    if account_match == '*' and client.user.account != '*':
        return 1
    if account_match == '0' and client.user.account == '*':
        return 1
    if account_match.lower() == client.user.account.lower():
        return 1


class AccountBan:
    name = "account"
    flag = "a"
    paramcount = 1

    # Checks if the param is valid, in which case it returns it.
    is_ok = account_is_valid

    # Called by Channel.is_banned() and takes the client, channel, and the mask.
    is_match = account_is_match


def init(module):
    Extban.add(AccountBan)
    Isupport.add("ACCOUNTEXTBAN", AccountBan.name + ',' + AccountBan.flag)
