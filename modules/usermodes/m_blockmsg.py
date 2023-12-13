"""
provides usermodes +R, +Z, and +D to block private messages
"""

from handle.core import Usermode, Numeric, Hook


def blockmsg_RZD(client, to_client, msg, sendtype):
    # if 'o' in client.user.modes:
    #     return msg

    if 'D' in to_client.user.modes:
        client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "This user does not accept private messages")
        return Hook.DENY

    if 'R' in to_client.user.modes:
        if 'r' not in client.user.modes:
            client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "You need a registered nickname to talk privately to this user")
            return Hook.DENY
        if 'r' not in to_client.user.modes:
            client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "Message not sent. Recipient has usermode +R but is not using a registered nickname")
            return Hook.DENY

    if 'R' in client.user.modes:
        if 'r' not in client.user.modes:
            client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "Message not sent. You have usermode +R but are not using a registered nickname")
            return Hook.DENY
        if 'r' not in to_client.user.modes:
            client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "Message not sent. You have usermode +R but recipient is not using a registered nickname")
            return Hook.DENY

    if 'Z' in to_client.user.modes:
        if 'z' not in client.user.modes:
            client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "You need to be on a secure connection to talk privately to this user")
            return Hook.DENY
        if 'z' not in to_client.user.modes:
            client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "Message not sent. Recipient has usermode +Z but is not using a secure connection")
            return Hook.DENY

    if 'Z' in client.user.modes:
        if 'z' not in client.user.modes:
            client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "Message not sent. You have usermode +Z but are not using a secure connection")
            return Hook.DENY
        if 'z' not in to_client.user.modes:
            client.sendnumeric(Numeric.ERR_CANTSENDTOUSER, to_client.name, "Message not sent. You have usermode +Z but recipient is not using a secure connection")
            return Hook.DENY

    return msg


def init(module):
    Usermode.add(module, "R", 1, 0, Usermode.allow_all, "Only users with a registered nickname can private message you")
    Usermode.add(module, "Z", 1, 0, Usermode.allow_all, "Only users on a secure connection can private message you")
    Usermode.add(module, "D", 1, 0, Usermode.allow_all, "No-one can private message you")
    Hook.add(Hook.CAN_SEND_TO_USER, blockmsg_RZD)
