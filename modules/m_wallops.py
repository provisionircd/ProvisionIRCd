"""
/wallops command
"""

from handle.core import IRCD, Usermode, Command, Flag
from handle.logger import logging


def cmd_wallops(client, recv):
    msg = ' '.join(recv[1:]).removeprefix(':')
    for user_client in [c for c in IRCD.local_users() if 'w' in c.user.modes]:
        user_client.send([], f":{client.fullmask} WALLOPS :{msg}")

    data = f":{client.id} WALLOPS :{msg}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Usermode.add(module, 'w', 1, 0, Usermode.allow_all, "Can see wallops messages")
    Command.add(module, cmd_wallops, "WALLOPS", 1, Flag.CMD_OPER)
