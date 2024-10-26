"""
msgid capability
"""

from handle.core import MessageTag, Hook, Isupport

import secrets
import time
import base64


class MessageId(MessageTag):
    name = "msgid"

    def __init__(self, value):
        super().__init__(name=MessageId.name, value=value)


def get_msgid(client):
    random_bytes = secrets.token_bytes(8)
    timestamp = (int(time.time_ns()) & ((1 << 48) - 1)).to_bytes(6, "big")
    combined = random_bytes + timestamp + secrets.token_bytes(2)
    msgid = base64.b64encode(combined).decode("utf-8").rstrip('=')
    msgid = msgid.replace('+', 'A').replace('/', 'B')
    msgid = msgid[:22]
    return msgid


def add_msgid(client):
    # msgid = str(uuid.uuid1()).replace('-', '')[:22]
    msgid = get_msgid(client)
    tag = MessageId(value=msgid)
    client.mtags.append(tag)


def init(module):
    Hook.add(Hook.NEW_MESSAGE, add_msgid)
    MessageTag.add(MessageId)
    Isupport.add("MSGREFTYPES", MessageId.name)
