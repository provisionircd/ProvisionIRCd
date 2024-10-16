"""
userhost and userip tags
"""

from handle.core import IRCD, MessageTag, Hook


class UserhostTag(MessageTag):
    name = "userhost"

    def __init__(self, value):
        super().__init__(name=f"{IRCD.me.name}/{UserhostTag.name}", value=value)

    def is_visible_to(self, to_client):
        return super().is_visible_to(to_client) and (to_client.server or 'o' in to_client.user.modes)


class UseripTag(MessageTag):
    name = "userip"

    def __init__(self, value):
        super().__init__(name=f"{IRCD.me.name}/{UseripTag.name}", value=value)

    def is_visible_to(self, to_client):
        return super().is_visible_to(to_client) and (to_client.server or 'o' in to_client.user.modes)


def add_userhosttag(client):
    if client.user:
        tag = UserhostTag(value=client.user.realhost)
        client.mtags.append(tag)


def add_useriptag(client):
    if client.user:
        tag = UseripTag(value=client.ip)
        client.mtags.append(tag)


def init(module):
    Hook.add(Hook.NEW_MESSAGE, add_userhosttag)
    Hook.add(Hook.NEW_MESSAGE, add_useriptag)
    MessageTag.add(UserhostTag)
    MessageTag.add(UseripTag)
