"""
/svsjoin and /svspart command (server)
"""

from handle.core import IRCD, Command, Flag
from handle.logger import logging


def cmd_svspartjoin(client, recv):
    if not (part_cmd := Command.find_command(client, "PART")) or not (join_cmd := Command.find_command(client, "JOIN")):
        return
    if not (target := IRCD.find_user(recv[1])):
        return

    match recv[0].lower():
        case "svsjoin":
            if target.local:
                join_cmd.do(target, "JOIN", recv[2])
            data = f":{client.id} SVSJOIN {target.name} {recv[2]}"
            IRCD.send_to_servers(client, [], data)

        case "svspart":
            if target.local:
                part_cmd.do(target, "PART", recv[2])
            data = f":{client.id} SVSPART {target.name} {recv[2]}"
            IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_svspartjoin, "SVSJOIN", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_svspartjoin, "SVSPART", 2, Flag.CMD_SERVER)
