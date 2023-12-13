"""
blocks /list commands for newly connected users
"""

from time import time

from handle.core import IRCD, Hook, Numeric

delay = 30


def delaylist(client, recv):
    if recv[0].lower() == "list" and int(time()) - client.creationtime <= delay and 'o' not in client.user.modes:
        IRCD.server_notice(client, "*** Please wait a while before requesting channel list.")
        client.sendnumeric(Numeric.RPL_LISTEND)
        return Hook.DENY
    return Hook.CONTINUE


def init(module):
    Hook.add(Hook.PRE_COMMAND, delaylist)


def unload(ircd):
    Hook.remove(delaylist)
