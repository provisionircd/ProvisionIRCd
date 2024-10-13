"""
oper-tag capability
"""

from handle.core import IRCD, MessageTag, Hook


class OperTag(MessageTag):
    name = "oper"

    def __init__(self, value):
        super().__init__(name=f"{IRCD.me.name}/{OperTag.name}", value=value)

    def is_visible_to(self, to_client):
        return super().is_visible_to(to_client)

    def filter_value(self, target) -> MessageTag:
        if target.user and 'o' not in target.user.modes:
            tag = OperTag(value=None)
            tag.name = self.name
            return tag


def add_opertag(client):
    if client.user and client.local and client.user.operclass \
            and 'o' in client.user.modes and 'H' not in client.user.modes:
        tag = OperTag(value=client.user.operclass.name)
        client.mtags.append(tag)


def init(module):
    Hook.add(Hook.NEW_MESSAGE, add_opertag)
    MessageTag.add(OperTag)
