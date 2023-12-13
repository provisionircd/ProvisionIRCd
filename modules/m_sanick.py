"""
/sanick command
"""

from handle.core import IRCD, Command, Numeric, Flag
from handle.logger import logging


def cmd_sanick(client, recv):
    if not (nick_cmd := Command.find_command(client, "NICK")):
        return

    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    if client.local:
        if not target.local and not client.has_permission("sacmds:sanick:global"):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
        if not client.has_permission("sacmds:sanick:local"):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

        client.local.flood_penalty += 100000

    if 'S' in target.user.modes or target.ulined or target.is_service:
        return IRCD.server_notice(client, f"*** You cannot use /SANICK on services.")

    if target.name == recv[2]:
        return

    if recv[2][0].isdigit():
        return IRCD.server_notice(client, "*** Nicknames may not start with a number")

    if nick_client := IRCD.find_user(recv[2]):
        return IRCD.server_notice(client, f"*** Nickname {nick_client.name} is already in use")

    newnick = recv[2][:IRCD.NICKLEN]
    for c in newnick:
        if c.lower() not in IRCD.NICKCHARS:
            return client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, newnick, c)

    if not newnick:
        return

    event = "LOCAL_SANICK" if target.local else "REMOTE_SANICK"
    msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) used SANICK to change {target.name}'s nickname to {newnick}"
    IRCD.log(client, "info", "sanick", event, msg, sync=0)

    data = f":{client.id} SANICK {target.name} {newnick}"
    IRCD.send_to_servers(client, [], data)

    if target.local:
        target.add_flag(Flag.CLIENT_USER_SANICK)
        nick_cmd.do(target, "NICK", newnick)
        target.flags.remove(Flag.CLIENT_USER_SANICK)
        msg = f"*** Your nickname has been forcefully changed to {target.name}."
        IRCD.server_notice(target, msg)


def init(module):
    Command.add(module, cmd_sanick, "SANICK", 2, Flag.CMD_OPER)
