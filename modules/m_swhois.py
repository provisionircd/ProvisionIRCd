"""
/swhois command (server)
"""

from handle.core import Command, IRCD, Flag
from handle.logger import logging


def cmd_swhois(client, recv):
    # :001 SWHOIS + nickname :[swhois]
    if not (target_client := IRCD.find_user(recv[2])):
        return

    if len(recv) < 4:
        # :001 SWHOIS - <client_id>
        # Clear SWHOIS.
        target_client.user.swhois = []
        IRCD.send_to_servers(client, [], recv)
        return

    line = ' '.join(recv[3:]).removeprefix(":")

    if recv[1] == '-':
        target_client.del_swhois(line)

    elif recv[1] == '+':
        target_client.add_swhois(line)

    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_swhois, "SWHOIS", 2, Flag.CMD_SERVER)
