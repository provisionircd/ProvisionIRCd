"""
/monitor command
"""

# Draft:
# https://ircv3.net/specs/core/monitor-3.2

import time

from handle.core import IRCD, Command, Isupport, Numeric, Hook
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
    if int(time.time()) - client.creationtime > 10:
        client.local.flood_penalty += 100000
    try:
        if recv[1] not in 'CLS+-':
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
                is_online = next((u.fullmask for u in IRCD.global_clients() if u.name.lower() == target.lower()), 0)
                if is_online:
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
                buffer_length = len(' '.join(buffer))
                if buffer_length >= 400:
                    all_targets = ' '.join(buffer)
                    client.sendnumeric(Numeric.RPL_MONLIST, all_targets)
                    buffer = []
                    continue
            if buffer:
                client.sendnumeric(Numeric.RPL_MONLIST, ' '.join(buffer))
            client.sendnumeric(Numeric.RPL_ENDOFMONLIST)

        elif recv[1] == 'S':
            online_buffer, offline_buffer = [], []
            processed = []
            for target in Monitor.monlist[client]:
                is_online = next((u.name for u in IRCD.global_clients() if u.name.lower() == target.lower()), 0)
                mon_target = target if not is_online else is_online
                if mon_target in processed:
                    continue
                processed.append(mon_target)
                if is_online:
                    online_buffer.append(mon_target)
                    buffer_length = len(' '.join(online_buffer))
                    if buffer_length >= 400:
                        all_targets = ' '.join(online_buffer)
                        client.sendnumeric(Numeric.RPL_MONONLINE, all_targets)
                        online_buffer = []
                        continue
                else:
                    offline_buffer.append(mon_target)
                    buffer_length = len(' '.join(offline_buffer))
                    if buffer_length >= 400:
                        all_targets = ' '.join(offline_buffer)
                        client.sendnumeric(Numeric.RPL_MONOFFLINE, all_targets)
                        offline_buffer = []
                        continue
            if online_buffer:
                client.sendnumeric(Numeric.RPL_MONONLINE, ' '.join(online_buffer))
            if offline_buffer:
                client.sendnumeric(Numeric.RPL_MONOFFLINE, ' '.join(offline_buffer))

    except Exception as ex:
        logging.exception(ex)


def mon_connect(client):
    mon_notify = [u for u in IRCD.global_users() if u in Monitor.monlist and client.name.lower() in [x.lower() for x in Monitor.monlist[u]]]
    for user in mon_notify:
        user.sendnumeric(Numeric.RPL_MONONLINE, client.fullmask)


def mon_quit(client, reason):
    mon_notify = [u for u in IRCD.global_users() if u in Monitor.monlist and client.name.lower() in [x.lower() for x in Monitor.monlist[u]]]
    for user in mon_notify:
        user.sendnumeric(Numeric.RPL_MONOFFLINE, client.fullmask)
    if client in Monitor.monlist:
        del Monitor.monlist[client]


def mon_nickchange(client, newnick):
    mon_notify_on = [u for u in IRCD.global_users() if u in Monitor.monlist and newnick.lower() in [x.lower() for x in Monitor.monlist[u]]]
    mon_notify_off = [u for u in IRCD.global_users() if u in Monitor.monlist and client.name.lower() in [x.lower() for x in Monitor.monlist[u]]]
    for user in mon_notify_on:
        user.sendnumeric(Numeric.RPL_MONONLINE, f"{newnick}!{client.user.username}@{client.user.cloakhost}")
    for user in mon_notify_off:
        user.sendnumeric(Numeric.RPL_MONOFFLINE, client.fullmask)


def init(module):
    Isupport.add("MONITOR", MAXMONITOR)
    Hook.add(Hook.LOCAL_CONNECT, mon_connect)
    Hook.add(Hook.REMOTE_CONNECT, mon_connect)
    Hook.add(Hook.LOCAL_QUIT, mon_quit)
    Hook.add(Hook.REMOTE_QUIT, mon_quit)
    Hook.add(Hook.LOCAL_NICKCHANGE, mon_nickchange)
    Hook.add(Hook.REMOTE_NICKCHANGE, mon_nickchange)
    Command.add(module, cmd_monitor, "MONITOR", 1)
