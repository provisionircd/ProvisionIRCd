"""
operclass bans/exceptions/invex
~operclass:name_of_operclass
"""

from classes.data import Extban
from handle.functions import is_match


def operclass_is_valid(client, channel, action, mode, param):
    if 'o' not in client.user.modes or len(param.split(':')) < 2:
        return 0

    return param


def operclass_is_match(client, channel, mask):
    """ mask == raw ban entry from a channel """
    if not client.user.operclass:
        return 0
    operclass = mask.split(':')[1]
    if is_match(operclass, client.user.operclass.name):
        return 1


class OperclassExtban:
    name = "operclass"
    flag = 'O'

    # Checks if the param is valid, in which case it returns it.
    is_ok = operclass_is_valid

    # Called by Channel.is_banned() and takes the client and the mask.
    is_match = operclass_is_match


def init(module):
    Extban.add(OperclassExtban)
