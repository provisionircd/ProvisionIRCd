"""
account-tag capability
"""

from handle.logger import logging
from handle.core import Capability, MessageTag, Hook


class AccountTag(MessageTag):
    name = "account"

    def __init__(self, value):
        super().__init__(name=AccountTag.name, value=value)

    def is_visible_to(self, to_client):
        return super().is_visible_to(to_client) or to_client.has_capability("account-tag")


def add_account_tag(client):
    if client.user and "r" in client.user.modes and client.user.account != "*":
        client.mtags.append(AccountTag(value=client.user.account))


def init(module):
    Capability.add("account-tag")
    Hook.add(Hook.NEW_MESSAGE, add_account_tag)
    MessageTag.add(AccountTag)
