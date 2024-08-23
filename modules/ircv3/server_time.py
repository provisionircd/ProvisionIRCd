"""
server-time capability
"""

from handle.core import MessageTag, Capability, IRCD, Hook


class ServerTime(MessageTag):
    name = "time"

    def __init__(self, value):
        super().__init__(name=ServerTime.name, value=value)

    def is_visible_to(self, to_client):
        return super().is_visible_to(to_client) or to_client.has_capability("server-time")


def add_server_time(client):
    time_tag = ServerTime(value=IRCD.get_time_string())
    client.mtags.append(time_tag)


def init(module):
    Capability.add("server-time")
    Hook.add(Hook.NEW_MESSAGE, add_server_time)
    MessageTag.add(ServerTime)
