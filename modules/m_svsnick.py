"""
/svsnick command (server)
"""

from handle.core import IRCD, Command, Flag
from handle.logger import logging


def cmd_svsnick(client, recv):
    if not (nick_cmd := Command.find_command(client, "NICK")):
        return

    if not (target := IRCD.find_user(recv[1])):
        return

    if target.name == recv[2] or recv[2][0].isdigit() or IRCD.find_user(recv[2]):
        return

    newnick = recv[2][:IRCD.NICKLEN]
    for c in newnick:
        if c.lower() not in IRCD.NICKCHARS:
            return

    if not newnick:
        return

    data = f":{client.id} SVSNICK {target.name} {newnick}"
    IRCD.send_to_servers(client, [], data)

    if target.local:
        target.add_flag(Flag.CLIENT_USER_SANICK)
        nick_cmd.do(target, "NICK", newnick)
        target.flags.remove(Flag.CLIENT_USER_SANICK)


def init(module):
    Command.add(module, cmd_svsnick, "SVSNICK", 2, Flag.CMD_SERVER)
