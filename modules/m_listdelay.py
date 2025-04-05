"""
blocks /list commands for newly connected users
"""

from handle.core import IRCD, Hook, Numeric, Isupport


def delaylist(client, recv):
    if recv[0].lower() == "list" and client.seconds_since_signon() < 10 and 'o' not in client.user.modes:
        IRCD.server_notice(client, "*** Please wait a while before requesting channel list.")
        client.sendnumeric(Numeric.RPL_LISTEND)
        return Hook.DENY
    return Hook.CONTINUE


def init(module):
    Hook.add(Hook.PRE_COMMAND, delaylist)
    Isupport.add("SECURELIST")
