"""
/monitor command
"""

# Draft:
# https://ircv3.net/specs/core/monitor-3.2

from handle.core import IRCD, Command, Isupport, Numeric, Hook, Capability
from handle.logger import logging

MAXMONITOR = 200


class Monitor:
    """
    Maintain your MONITOR list. You will be notified when a nickname on your MONITOR list
    connects or disconnects, even if you don't share a channel.
    Your watchlist will be cleared when you disconnect.
    -
    Add a nickname:             /MONITOR + nickname1[,nickname2]
    Remove a nickname:          /MONITOR - nickname1[,nickname2]
    View monitor list:          /MONITOR <param>
    Param C:                    Clears your monitor list.
    Param L:                    Displays your entire monitor list.
    Param S:                    Displays entire monitor list, with status.
    """

    monlist = {}


def cmd_monitor(client, recv):
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
                skip_target = 0
                if target.lower() in monlist_lower:
                    continue
                if len(Monitor.monlist[client]) >= MAXMONITOR:
                    return client.sendnumeric(Numeric.RPL_MONLISTFULL)
                for c in target:
                    if c.lower() not in IRCD.NICKCHARS:
                        skip_target = 1
                if skip_target:
                    continue
                Monitor.monlist[client].append(target)
                if is_online := next((u.fullmask for u in IRCD.global_clients() if u.name.lower() == target.lower()), 0):
                    currently_online.append(is_online)

            buffer = []
            if currently_online:
                prefix = f":{IRCD.me.name} {Numeric.RPL_MONONLINE[0]} {client.name} :"
                prefix_len = len(prefix)
                max_len = 510 - prefix_len
                for user in currently_online:
                    len_now = len(','.join(buffer))
                    len_next = len_now + (len(user) + 1)  # Including separating comma.
                    if len_next >= max_len:
                        client.sendnumeric(Numeric.RPL_MONONLINE, ','.join(buffer))
                        buffer = [user]
                        continue
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
            for target in Monitor.monlist[client]:
                buffer.append(target)
                if len(' '.join(buffer)) >= 400:
                    client.sendnumeric(Numeric.RPL_MONLIST, ' '.join(buffer))
                    buffer.clear()
            if buffer:
                client.sendnumeric(Numeric.RPL_MONLIST, ' '.join(buffer))
            client.sendnumeric(Numeric.RPL_ENDOFMONLIST)

        elif recv[1] == 'S':
            online_buffer, offline_buffer = [], []
            for target in Monitor.monlist[client]:
                target_client = IRCD.find_user(target)
                buffer, numeric = (
                    (online_buffer, Numeric.RPL_MONONLINE) if target_client else
                    (offline_buffer, Numeric.RPL_MONOFFLINE)
                )
                buffer.append(target_client.fullmask if target_client else target)
                if len(' '.join(buffer)) >= 400:
                    client.sendnumeric(numeric, ' '.join(buffer))
                    buffer.clear()
            if online_buffer:
                client.sendnumeric(Numeric.RPL_MONONLINE, ' '.join(online_buffer))
            if offline_buffer:
                client.sendnumeric(Numeric.RPL_MONOFFLINE, ' '.join(offline_buffer))

    except Exception as ex:
        logging.exception(ex)


def mon_connect(client):
    mon_notify = [u for u in IRCD.local_users() if u in Monitor.monlist and client.name.lower() in [x.lower() for x in Monitor.monlist[u]]]
    for user in mon_notify:
        user.sendnumeric(Numeric.RPL_MONONLINE, client.fullmask)


def mon_quit(client, reason):
    mon_notify = [u for u in IRCD.local_users() if u in Monitor.monlist and client.name.lower() in [x.lower() for x in Monitor.monlist[u]]]
    for user in mon_notify:
        user.sendnumeric(Numeric.RPL_MONOFFLINE, client.fullmask)
    if client in Monitor.monlist:
        del Monitor.monlist[client]


def mon_nickchange(client, newnick):
    mon_notify_on = [u for u in IRCD.local_users() if u in Monitor.monlist and newnick.lower() in [x.lower() for x in Monitor.monlist[u]]]
    mon_notify_off = [u for u in IRCD.local_users() if u in Monitor.monlist and client.name.lower() in [x.lower() for x in Monitor.monlist[u]]]
    for user in mon_notify_on:
        user.sendnumeric(Numeric.RPL_MONONLINE, f"{newnick}!{client.user.username}@{client.user.cloakhost}")
    for user in mon_notify_off:
        user.sendnumeric(Numeric.RPL_MONOFFLINE, client.fullmask)


def monitor_event(client, monitor_type, new_ident=None, new_host=None):
    cap_map = {
        "away": "away-notify",
        "account": "account-notify",
        "chghost": "chghost",
        "setname": "setname"
    }

    cap = cap_map[monitor_type]
    data = ''

    for c in [c for c in IRCD.local_users(cap=cap) if not IRCD.common_channels(client, c) and c.has_capability("extended-monitor")]:
        if monitor_type == "away":
            data = f":{client.fullmask} AWAY {':' + client.user.away if client.user.away else ''}"
        elif monitor_type == "account":
            data = f":{client.fullmask} ACCOUNT {client.user.account}"
        elif monitor_type == "chghost":
            data = f":{client.fullmask} CHGHOST {new_ident} {new_host}"
        elif monitor_type == "setname":
            data = f":{client.fullmask} SETNAME :{client.info}"

        c.send([], data)


def monitor_away(client, awaymsg):
    monitor_event(client, "away")


def monitor_account(client):
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
    Hook.add(Hook.LOCAL_CHGHOST, monitor_chghost)
    Hook.add(Hook.LOCAL_SETNAME, monitor_setname)
    Isupport.add("MONITOR", MAXMONITOR)
    Capability.add("extended-monitor")
