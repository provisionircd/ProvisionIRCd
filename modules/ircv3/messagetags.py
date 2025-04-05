"""
message-tags capability
"""

from dataclasses import dataclass
from typing import ClassVar

from handle.core import IRCD, Isupport, Numeric, Flag, Command, Capability
from handle.logger import logging


@dataclass
class MessageTag:
    table: ClassVar[list] = []

    name: str = ''
    value: str = ''
    value_required: int = 0
    local: int = 0
    client_tag: int = 0

    @classmethod
    def is_client_tag(cls):
        return cls.client_tag or cls.name.startswith('+')

    def is_visible_to(self, to_client):
        if (tag := MessageTag.find_tag(self.name)) and (tag.local or self.local) and to_client.server:
            # logging.debug(f"Not relaying local tag {self} to server {self.name}")
            return 0
        return to_client.has_capability("message-tags")

    def filter_value(self, target):
        """
        Do nothing by default.
        """
        pass

    def value_is_ok(self, value):
        return 1

    @property
    def string(self):
        return f"{self.name}{'=' + self.value if self.value else ''}"

    @staticmethod
    def find_tag(name):
        for tag in MessageTag.table:
            if tag.name == name or any(value == tag.name for value in name.split('/')):
                return tag

    @staticmethod
    def add(tag):
        MessageTag.table.append(tag)

    @staticmethod
    def filter_tags(mtags, destination):
        return_tags = list(mtags)

        for index, tag in enumerate(mtags):
            if not tag.is_visible_to(destination) or (tag.value_required and not tag.value):
                return_tags[index] = None
            else:
                if filtered_tag := tag.filter_value(destination):
                    return_tags[index] = filtered_tag

        return_tags = [tag for tag in return_tags if tag]

        return return_tags


def cmd_tagmsg(client, recv):
    if not client.recv_mtags or len(recv[1]) < 2:
        return

    recv_target = recv[1]
    prefix = ''
    if recv_target[0] in IRCD.get_member_prefix_str_sorted():
        prefix = recv_target[0]
        recv_target = recv_target[1:]

    if recv_target[0] in IRCD.CHANPREFIXES + IRCD.get_member_prefix_str_sorted():
        if not (target := IRCD.find_channel(recv_target)):
            return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv_target)
        broadcast = [c for c in target.clients(client_cap="message-tags", prefix=prefix) if c != client]
    else:
        if not (target := IRCD.find_client(recv_target, user=1)):
            return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv_target)
        if target == client and not client.has_capability("echo-message") or not client.has_capability("message-tags"):
            return
        broadcast = [target]

    """ Add client-tags to .mtags list. """
    mtags = client.recv_mtags
    existing_names = {mtag.name for mtag in mtags}
    mtags.extend(tag for tag in client.mtags if tag.name not in existing_names)
    client.mtags = mtags

    for user in broadcast:
        user.send(client.mtags, f":{client.fullmask} TAGMSG {target.name}")

    IRCD.send_to_servers(client, client.mtags, f":{client.id} TAGMSG {target.name}")


def init(module):
    Capability.add("message-tags")
    Command.add(module, cmd_tagmsg, "TAGMSG", 1, Flag.CMD_USER, Flag.CMD_SERVER)
    Isupport.add("MTAGS", server_isupport=1)
