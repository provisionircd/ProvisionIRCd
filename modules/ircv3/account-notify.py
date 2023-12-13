"""
account-notify capability
"""

from handle.core import IRCD, Capability, Hook


def user_login(client):
    data = f":{client.fullmask} ACCOUNT {client.user.account}"
    IRCD.send_to_local_common_chans(client, mtags=[], client_cap="account-notify", data=data)


def init(module):
    Capability.add("account-notify")
    Hook.add(Hook.ACCOUNT_LOGIN, user_login)
