from handle.core import IRCD, Numeric, Command, Hook


def account_nickchange(client, newnick):
    if 'r' in client.user.modes and newnick.lower() != client.user.account.lower():
        client.user.modes = client.user.modes.replace('r', '')
        data = f":{IRCD.me.name} MODE {client.name} -r"
        client.send([], data)
        data = f":{client.id} MODE {client.name} -r"
        IRCD.send_to_servers(client, [], data)

    # if 'r' not in client.user.modes and newnick.lower() == client.user.account.lower():
    #     client.user.modes += 'r'
    #     data = f":{IRCD.me.name} MODE {client.name} +r"
    #     client.send([], data)
    #     data = f":{client.id} MODE {client.name} +r"
    #     IRCD.send_to_servers(client, [], data)


def account_changed(client):
    if client.user.account == '*':
        client.sendnumeric(Numeric.RPL_LOGGEDOUT, client.fullrealhost)
        # if 'r' in client.user.modes:
        #     client.user.modes = client.user.modes.replace('r', '')
        #     data = f":{client.name} MODE {client.name} -r"
        #     client.send([], data)
        #     data = f":{client.id} MODE {client.name} -r"
        #     if client.registered:
        #         IRCD.send_to_servers(client, [], data)
    else:
        client.sendnumeric(Numeric.RPL_LOGGEDIN, client.fullrealhost, client.user.account, client.user.account)


def account_usermode(client):
    if "r" not in client.user.modes and client.name == client.user.account:
        client.user.modes += "r"
        data = f":{client.name} MODE {client.name} +r"
        client.send([], data)
        data = f":{client.id} MODE {client.name} +r"
        IRCD.send_to_servers(client, [], data)


def account_whois(client, whois_client, lines):
    if whois_client.user.account != '*':
        line = Numeric.RPL_WHOISACCOUNT, whois_client.name, whois_client.user.account
        lines.append(line)


def cmd_logout(client, recv):
    if client.user.account == "*":
        return
    client.user.account = "*"
    if 'r' in client.user.modes:
        client.user.modes = client.user.modes.replace('r', '')
        data = f":{client.name} MODE {client.name} -r"
        client.send([], data)
        data = f":{client.id} MODE {client.name} -r"
        IRCD.send_to_servers(client, [], data)
    client.sendnumeric(Numeric.RPL_LOGGEDOUT)


def init(module):
    Hook.add(Hook.ACCOUNT_LOGIN, account_changed)
    Hook.add(Hook.WHOIS, account_whois)
    Hook.add(Hook.LOCAL_NICKCHANGE, account_nickchange)
    # Hook.add(Hook.LOCAL_CONNECT, account_usermode)
    Command.add(module, cmd_logout, "LOGOUT")
