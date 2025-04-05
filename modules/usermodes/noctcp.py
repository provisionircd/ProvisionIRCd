"""
user mode +T (block ctcp messages)
"""

from handle.core import Usermode, Hook, Numeric


def msg_noctcp(client, to_client, message, sendtype):
    if client.has_permission("immune:message:ctcp") or client.is_uline() or client == to_client:
        return Hook.CONTINUE

    if 'T' in to_client.user.modes and message[0] == '' and message[-1] == '':
        client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "This user does not accept CTCP messages")
        return Hook.DENY

    return Hook.CONTINUE


def init(module):
    Usermode.add(module, 'T', 1, 0, Usermode.allow_all, "Blocks CTCP messages")
    Hook.add(Hook.CAN_SEND_TO_USER, msg_noctcp)
