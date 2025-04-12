"""
userhost and userip tags
"""

from handle.core import IRCD, Hook, Capability
from modules.ircv3.messagetags import MessageTag


class BaseHostTag(MessageTag):
    name = None

    def __init__(self, value):
        if self.name is None:
            raise NotImplementedError(f"Subclass of BaseHostTag must define 'name'")
        super().__init__(name=f"provisionircd/{self.name}", value=value)

    def is_visible_to(self, to_client):
        return super().is_visible_to(to_client) and (to_client.server or 'o' in to_client.user.modes)


class HostTag(BaseHostTag):
    name = "host"


class IpTag(BaseHostTag):
    name = "ip"


def add_userhosttag(client):
    if client.user:
        client.mtags.append(HostTag(value=client.user.realhost))
        client.mtags.append(IpTag(value=client.ip))


def post_load(module):
    Capability.add("provisionircd/host")
    Capability.add("provisionircd/ip")
    Hook.add(Hook.NEW_MESSAGE, add_userhosttag)
    MessageTag.add(HostTag)
    MessageTag.add(IpTag)
