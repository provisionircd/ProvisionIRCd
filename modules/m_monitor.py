"""
/monitor command
"""

# Draft:
# https://ircv3.net/specs/core/monitor-3.2

from handle.core import IRCD, Command, Isupport, Numeric, Hook, Capability
from handle.logger import logging

MAXMONITOR = 200


class Monitor:
    monlist = {}


def cmd_monitor(client, recv):
    """
    Maintain your MONITOR list. You will be notified when a nickname on your MONITOR list
    connects or disconnects, even if you don't share a channel.
    Your watchlist will be cleared when you disconnect.
    -
    Add a nickname:             MONITOR + nickname1[,nickname2]
    Remove a nickname:          MONITOR - nickname1[,nickname2]
    View monitor list:          MONITOR <param>
    Param C:                    Clears your monitor list.
    Param L:                    Displays your entire monitor list.
    Param S:                    Displays entire monitor list, with status.
    """

    if client.seconds_since_signon() > 5:
        client.local.flood_penalty += 10_000
    try:
        if recv[1] not in "CLS+-":
            return
        if client not in Monitor.monlist:
            Monitor.monlist[client] = []

        monlist_lower = [x.lower() for x in Monitor.monlist[client]]
        if recv[1] == '+':
            currently_online = []
            for target in recv[2].split(','):
                if target.lower() in monlist_lower:
                    continue
                if len(Monitor.monlist[client]) >= MAXMONITOR:
                    return client.sendnumeric(Numeric.RPL_MONLISTFULL)
                if any(c.lower() not in IRCD.NICKCHARS for c in target):
                    continue

                Monitor.monlist[client].append(target)

                if is_online := next((u.fullmask for u in IRCD.get_clients(user=1) if u.name.lower() == target.lower()), 0):
                    currently_online.append(is_online)

            buffer = []
            if currently_online:
                prefix = f":{IRCD.me.name} {Numeric.RPL_MONONLINE[0]} {client.name} :"
                max_len = 510 - len(prefix)

                for user in currently_online:
                    buffer_str = ','.join(buffer)
                    if buffer and len(buffer_str) + len(user) + 1 >= max_len:
                        client.sendnumeric(Numeric.RPL_MONONLINE, buffer_str)
                        buffer = [user]
                    else:
                        buffer.append(user)

                if buffer:
                    client.sendnumeric(Numeric.RPL_MONONLINE, ','.join(buffer))

        elif recv[1] == '-':
            for target in recv[2].split(','):
                is_in_monlist = next((e for e in Monitor.monlist[client] if e.lower() == target.lower()), 0)
                if is_in_monlist:
                    Monitor.monlist[client].remove(is_in_monlist)

        elif recv[1] == 'C':
            Monitor.monlist[client] = []

        elif recv[1] == 'L':
            buffer = []
            buffer_size = 0
            max_size = 400

            for target in Monitor.monlist[client]:
                target_size = len(target) + (1 if buffer else 0)

                if buffer_size + target_size >= max_size:
                    client.sendnumeric(Numeric.RPL_MONLIST, ' '.join(buffer))
                    buffer = [target]
                    buffer_size = len(target)
                else:
                    buffer.append(target)
                    buffer_size += target_size

            if buffer:
                client.sendnumeric(Numeric.RPL_MONLIST, ' '.join(buffer))
            client.sendnumeric(Numeric.RPL_ENDOFMONLIST)

        elif recv[1] == 'S':
            online_buffer, offline_buffer = [], []

            for target in Monitor.monlist[client]:
                target_client = IRCD.find_client(target)

                if target_client:
                    buffer = online_buffer
                    numeric = Numeric.RPL_MONONLINE
                    value = target_client.fullmask
                else:
                    buffer = offline_buffer
                    numeric = Numeric.RPL_MONOFFLINE
                    value = target

                buffer.append(value)

                if len(' '.join(buffer)) >= 400:
                    client.sendnumeric(numeric, ' '.join(buffer))
                    buffer.clear()

            for buffer, numeric in [(online_buffer, Numeric.RPL_MONONLINE), (offline_buffer, Numeric.RPL_MONOFFLINE)]:
                if buffer:
                    client.sendnumeric(numeric, ' '.join(buffer))

    except Exception as ex:
        logging.exception(ex)


def mon_connect(client):
    for user in IRCD.get_clients(user=1):
        if user in Monitor.monlist and any(target.lower() == client.name.lower() for target in Monitor.monlist[user]):
            user.sendnumeric(Numeric.RPL_MONONLINE, client.fullmask)


def mon_quit(client, reason):
    for user in IRCD.get_clients(user=1):
        if user in Monitor.monlist and any(target.lower() == client.name.lower() for target in Monitor.monlist[user]):
            user.sendnumeric(Numeric.RPL_MONOFFLINE, client.fullmask)

    if client in Monitor.monlist:
        del Monitor.monlist[client]


def mon_nickchange(client, newnick):
    for user in IRCD.get_clients(user=1, local=1):
        if not (monlist := Monitor.monlist.get(user)):
            continue
        if any(n.lower() == newnick.lower() for n in monlist):
            user.sendnumeric(Numeric.RPL_MONONLINE, f"{newnick}!{client.user.username}@{client.user.host}")
        if any(n.lower() == client.name.lower() for n in monlist):
            user.sendnumeric(Numeric.RPL_MONOFFLINE, client.fullmask)


def monitor_event(client, monitor_type, new_ident=None, new_host=None):
    cap_map = {
        "away": "away-notify",
        "account": "account-notify",
        "chghost": "chghost",
        "setname": "setname"
    }

    format_map = {
        "away": lambda: f":{client.fullmask} AWAY {':' + client.user.away if client.user.away else ''}",
        "account": lambda: f":{client.fullmask} ACCOUNT {client.user.account}",
        "chghost": lambda: f":{client.fullmask} CHGHOST {new_ident} {new_host}",
        "setname": lambda: f":{client.fullmask} SETNAME :{client.info}"
    }

    cap = cap_map[monitor_type]
    data = format_map[monitor_type]()

    for c in (r for r in IRCD.get_clients(local=1, user=1, cap=cap) if r != client):
        monlist = Monitor.monlist.get(c)
        is_monitoring_client = monlist and any(n.lower() == client.name.lower() for n in monlist)
        meets_send_condition = not IRCD.common_channels(client, c) and c.has_capability("extended-monitor")
        if is_monitoring_client and meets_send_condition:
            c.send([], data)


def monitor_away(client, awaymsg):
    monitor_event(client, "away")


def monitor_account(client, old_account):
    monitor_event(client, "account")


def monitor_chghost(client, ident, host):
    monitor_event(client, "chghost", new_ident=ident, new_host=host)


def monitor_setname(client, newname):
    monitor_event(client, "setname")


def init(module):
    Command.add(module, cmd_monitor, "MONITOR", 1)
    Hook.add(Hook.LOCAL_CONNECT, mon_connect)
    Hook.add(Hook.REMOTE_CONNECT, mon_connect)
    Hook.add(Hook.LOCAL_QUIT, mon_quit)
    Hook.add(Hook.REMOTE_QUIT, mon_quit)
    Hook.add(Hook.LOCAL_NICKCHANGE, mon_nickchange)
    Hook.add(Hook.REMOTE_NICKCHANGE, mon_nickchange)
    Hook.add(Hook.AWAY, monitor_away)
    Hook.add(Hook.ACCOUNT_LOGIN, monitor_account)
    Hook.add(Hook.USERHOST_CHANGE, monitor_chghost)
    Hook.add(Hook.REALNAME_CHANGE, monitor_setname)
    Isupport.add("MONITOR", MAXMONITOR)
    Capability.add("extended-monitor")
