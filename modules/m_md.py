"""
/md command (server)
Exchange mod data between servers.
"""

from handle.core import IRCD, Command, Flag, MessageTag

from handle.logger import logging


class S2sMd(MessageTag):
    name = "s2s-md"

    def __init__(self, value):
        super().__init__(name=S2sMd.name, value=value)

    def is_visible_to(self, to_client):
        return super().is_visible_to(to_client) and to_client.server


def cmd_md(client, recv):
    if recv[1] == "client":
        if not (md_client := IRCD.find_user(recv[2])) and not (md_client := IRCD.find_server(recv[2])):
            # Closed early. Killed.
            return

        if value := recv[4].removeprefix(':'):
            md_client.add_md(name=recv[3], value=value)
        else:
            md_client.del_md(recv[3])


def init(module):
    Command.add(module, cmd_md, "MD", 3, Flag.CMD_SERVER)
    MessageTag.add(S2sMd)
