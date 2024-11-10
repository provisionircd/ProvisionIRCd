"""
Provides support for account names when logged in with services
"""

from handle.core import IRCD, Numeric, Hook


def account_nickchange(client, newnick):
    if 'r' in client.user.modes and newnick.lower() != client.user.account.lower():
        client.user.modes = client.user.modes.replace('r', '')
        data = f":{IRCD.me.name} MODE {client.name} -r"
        client.send([], data)
        data = f":{client.id} MODE {client.name} -r"
        IRCD.send_to_servers(client, [], data)


def account_changed(client):
    if client.user.account == '*':
        client.sendnumeric(Numeric.RPL_LOGGEDOUT, client.fullrealhost)
    else:
        client.sendnumeric(Numeric.RPL_LOGGEDIN, client.fullrealhost, client.user.account, client.user.account)


def account_whois(client, whois_client, lines):
    if whois_client.user.account != '*':
        line = Numeric.RPL_WHOISACCOUNT, whois_client.name, whois_client.user.account
        lines.append(line)


def account_check_connection(client):
    for require in [r for r in IRCD.configuration.requires if r.what == "authentication"]:
        if require.mask.is_match(client) and client.user.account == '*':
            msg = "You need to be logged into an account to connect to this server."
            if client.has_capability("standard-replies"):
                client.send([], f"FAIL * ACCOUNT_REQUIRED :{msg}")
            else:
                IRCD.server_notice(client, msg)
            return Hook.DENY
    return Hook.ALLOW


def init(module):
    Hook.add(Hook.PRE_CONNECT, account_check_connection)
    Hook.add(Hook.ACCOUNT_LOGIN, account_changed)
    Hook.add(Hook.WHOIS, account_whois)
    Hook.add(Hook.LOCAL_NICKCHANGE, account_nickchange)
