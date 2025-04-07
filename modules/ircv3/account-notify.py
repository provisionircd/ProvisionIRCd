"""
account-notify capability
"""

from handle.core import IRCD, Capability, Hook


def user_login(client, old_account):
    if (AccountTag := IRCD.get_attribute_from_module("AccountTag", package="modules.ircv3.account-tag")) and old_account != '*':
        client.mtags.append(AccountTag(value=old_account))
    data = f":{client.fullmask} ACCOUNT {client.user.account}"
    IRCD.send_to_local_common_chans(client, mtags=client.mtags, client_cap="account-notify", data=data)


def init(module):
    Capability.add("account-notify")
    Hook.add(Hook.ACCOUNT_LOGIN, user_login)
