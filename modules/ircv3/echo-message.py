"""
echo-message capability
"""

from handle.core import Capability, Hook
from handle.logger import logging


def return_message(client, target, message):
    if client.has_capability("echo-message") and 'd' not in client.user.modes:
        data = f":{client.name}!{client.user.username}@{client.user.cloakhost} PRIVMSG {target.name} :{message}"
        client.send(client.mtags, data)


def init(module):
    Capability.add("echo-message")
    Hook.add(Hook.LOCAL_CHANMSG, return_message)
    Hook.add(Hook.LOCAL_USERMSG, return_message)
