"""
/sendumode command (server)
"""

from handle.core import IRCD, Command, Flag, Client
from handle.logger import logging


def cmd_sendumode(client, recv):
    # 00B SENDUMODE o :message
    for user_client in [c for c in IRCD.local_users() if recv[1] in c.user.modes and c.local]:
        data = f":{client.name} NOTICE {user_client.name} {' '.join(recv[2:])}"
        user_client.send([], data)
    IRCD.send_to_servers(client, [], ' '.join(recv))


def cmd_sendsno(client, recv):
    flag = recv[1]
    message = " ".join(recv[2:]).removeprefix(':')
    IRCD.send_snomask(client, flag, message)
    # for c in [c for c in Client.table if c.user and c.local and flag in c.user.snomask]:
    #     data = f":{client.name} NOTICE {c.name} :{message}"
    #     c.send([], data)
    #
    # IRCD.send_to_servers(client, [], ' '.join(recv))


def init(module):
    Command.add(module, cmd_sendsno, "SENDSNO", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_sendumode, "SENDUMODE", 2, Flag.CMD_SERVER)
