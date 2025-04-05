"""
echo-message capability
"""

from handle.core import Capability, Hook


def echo_msg(client, target, message, cmd, prefix):
    if client.has_capability("echo-message") and 'd' not in client.user.modes:
        data = f":{client.name}!{client.user.username}@{client.user.host} {cmd} {prefix}{target.name} :{message}"
        client.send(client.mtags, data)


def return_message(client, target, message, prefix=''):
    echo_msg(client, target, message, "PRIVMSG", prefix)


def return_notice(client, target, message, prefix=''):
    echo_msg(client, target, message, "NOTICE", prefix)


def init(module):
    Capability.add("echo-message")
    Hook.add(Hook.LOCAL_CHANMSG, return_message)
    Hook.add(Hook.LOCAL_USERMSG, return_message)
    Hook.add(Hook.LOCAL_CHANNOTICE, return_notice)
    Hook.add(Hook.LOCAL_USERNOTICE, return_notice)
