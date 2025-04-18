"""
oper-tag capability
"""

from handle.core import IRCD, Hook, Capability
from modules.ircv3.messagetags import MessageTag


class OperTag(MessageTag):
    name = "oper"

    def __init__(self, value):
        super().__init__(name=f"provisionircd/{OperTag.name}", value=value)

    def filter_value(self, target) -> MessageTag | None:
        if target.user and 'o' not in target.user.modes:
            tag = OperTag(value=None)
            tag.name = self.name
            return tag


def add_opertag(client):
    if client.user and client.user.operclass and 'o' in client.user.modes and 'H' not in client.user.modes:
        tag = OperTag(value=client.user.operclass.name)
        client.mtags.append(tag)


def post_load(module):
    Capability.add("provisionircd/oper-tag")
    Hook.add(Hook.NEW_MESSAGE, add_opertag)
    MessageTag.add(OperTag)
