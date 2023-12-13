"""
/svskill command (server)
"""

from handle.core import IRCD, Command, Flag
from handle.logger import logging


def cmd_svskill(client, recv):
    if not (target := IRCD.find_user(recv[1])):
        return

    reason = ' '.join(recv[2:]).removeprefix(":")
    data = f':{client.id} SVSKILL {target.id} :{reason}'
    target.kill(reason, killed_by=client)
    IRCD.send_to_servers(client, mtags=[], data=data)


def init(module):
    Command.add(module, cmd_svskill, "SVSKILL", 2, Flag.CMD_SERVER)
