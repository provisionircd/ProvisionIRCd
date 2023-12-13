"""
msgid capability
"""

import uuid

from handle.core import MessageTag, Hook


class MessageId(MessageTag):
    name = "msgid"

    def __init__(self, value):
        super().__init__(name=MessageId.name, value=value)


def add_msgid(client):
    msgid = str(uuid.uuid1()).replace("-", "")[:20]
    tag = MessageId(value=msgid)
    client.mtags.append(tag)


def init(module):
    Hook.add(Hook.NEW_MESSAGE, add_msgid)
    MessageTag.add(MessageId)
