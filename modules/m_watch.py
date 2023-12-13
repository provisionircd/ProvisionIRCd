"""
/watch command
"""

import time

from handle.core import IRCD, Command, Isupport, Numeric, Hook
from handle.logger import logging

MAXWATCH = 200


class Watch:
    """
    Maintain your WATCH list. You will be notified when a nickname on your WATCH list
    connects or disconnects, even if you don't share a channel.
    Your watchlist will be cleared when you disconnect.
    -
    Add a nickname:             /WATCH +nickname
    Remove a nickname:          /WATCH -nickname
    View current online users:  /WATCH
    """

    watchlist = {}


def cmd_watch(client, recv):
    if int(time.time()) - client.creationtime >= 5:
        client.local.flood_penalty += 100000
    else:
        client.flood_safe_on()
    try:
        watch_lower = [x.lower() for x in Watch.watchlist[client]]
        if len(recv) == 1:
            watch_online = [user for user in IRCD.global_clients() if user.registered and user.name.lower() in watch_lower]
            for watch_client in watch_online:
                client.sendnumeric(Numeric.RPL_NOWON, watch_client.name, watch_client.user.username, watch_client.user.cloakhost, watch_client.creationtime)
            client.sendnumeric(Numeric.RPL_ENDOFWATCHLIST, 'l')
            return
        else:
            process_entries = recv[1:]
            for entry in process_entries:
                if entry[0] not in '+-':

                    if entry.lower() == 'C':
                        if len(recv) == 2:  # Clear.
                            Watch.watchlist[client] = []

                    elif entry.lower() == 'S':
                        for nick in Watch.watchlist[client]:
                            watch_client = [client for client in IRCD.global_clients() if client.name.lower() == nick.lower() and client.registered]
                            if watch_client:
                                watch_client = watch_client[0]
                                client.sendnumeric(Numeric.RPL_NOWON, watch_client.name, watch_client.user.username, watch_client.user.cloakhost, watch_client.creationtime)
                            else:
                                client.sendnumeric(Numeric.RPL_NOWOFF, nick, '*', '*', '0')
                        client.sendnumeric(Numeric.RPL_WATCHSTAT, len(Watch.watchlist[client]), 0)
                        client.sendnumeric(Numeric.RPL_WATCHLIST, " ".join(Watch.watchlist[client]))
                        client.sendnumeric(Numeric.RPL_ENDOFWATCHLIST, 'S')
                    continue
                nick = entry[1:]
                if entry[0] == '+':
                    if len(Watch.watchlist[client]) >= MAXWATCH:
                        return client.sendnumeric(Numeric.ERR_TOOMANYWATCH, nick)

                    if nick.lower() not in watch_lower:
                        Watch.watchlist[client].append(nick)

                    watch_client = [client for client in IRCD.global_clients() if client.name.lower() == nick.lower() and client.registered]
                    if watch_client:
                        watch_client = watch_client[0]
                        client.sendnumeric(Numeric.RPL_NOWON, watch_client.name, watch_client.user.username, watch_client.user.cloakhost, watch_client.creationtime)
                    else:
                        client.sendnumeric(Numeric.RPL_NOWOFF, nick, '*', '*', '0')

                elif entry[0] == '-':
                    if nick.lower() in watch_lower:
                        list_entry = [entry for entry in Watch.watchlist[client] if entry.lower() == nick.lower()]
                        list_entry = list_entry[0]
                        Watch.watchlist[client].remove(list_entry)
                        is_online = IRCD.find_user(nick)
                        ident = '*' if not is_online else is_online.user.username
                        cloakhost = '*' if not is_online else is_online.user.cloakhost
                        signon = '0' if not is_online else is_online.creationtime
                        client.sendnumeric(Numeric.RPL_WATCHOFF, list_entry, ident, cloakhost, signon)

    except Exception as ex:
        logging.exception(ex)


def watch_user_loggedon(client):
    if client not in Watch.watchlist:
        Watch.watchlist[client] = []
    watch_notify = [c for c in IRCD.global_users() if c in Watch.watchlist and client.name.lower() in [x.lower() for x in Watch.watchlist[c]] and not c.has_capability("monitor")]
    for user in watch_notify:
        user.sendnumeric(Numeric.RPL_LOGON, client.name, client.user.username, client.user.cloakhost, client.creationtime)


def watch_nickchange(client, nick):
    watch_notify_offline = [c for c in IRCD.global_users() if
                            c in Watch.watchlist and client.name.lower() in [x.lower() for x in Watch.watchlist[c]] and not c.has_capability("monitor")]
    watch_notify_online = [c for c in IRCD.global_users() if c in Watch.watchlist and nick.lower() in [x.lower() for x in Watch.watchlist[c]] and not c.has_capability("monitor")]
    for watch_user in watch_notify_offline:
        watch_user.sendnumeric(Numeric.RPL_LOGOFF, client.name, client.user.username, client.user.cloakhost, client.creationtime)
    for watch_user in watch_notify_online:
        watch_user.sendnumeric(Numeric.RPL_LOGON, nick, client.user.username, client.user.cloakhost, client.creationtime)


def watch_quit(client, reason):
    watch_notify_offline = [c for c in IRCD.global_users() if
                            c in Watch.watchlist and client.name.lower() in [x.lower() for x in Watch.watchlist[c]] and not c.has_capability("monitor")]
    for user in watch_notify_offline:
        user.sendnumeric(Numeric.RPL_LOGOFF, client.name, client.user.username, client.user.cloakhost, client.creationtime)
    if client in Watch.watchlist:
        del Watch.watchlist[client]


def watch_flood_safe(client, cmd, recv):
    if cmd.lower() == "watch":
        client.flood_safe_off()


def init(module):
    Hook.add(Hook.LOCAL_CONNECT, watch_user_loggedon)
    Hook.add(Hook.REMOTE_CONNECT, watch_user_loggedon)
    Hook.add(Hook.LOCAL_QUIT, watch_quit)
    Hook.add(Hook.REMOTE_QUIT, watch_quit)
    Hook.add(Hook.LOCAL_NICKCHANGE, watch_nickchange)
    Hook.add(Hook.REMOTE_NICKCHANGE, watch_nickchange)
    Hook.add(Hook.POST_COMMAND, watch_flood_safe)
    Isupport.add("WATCH", MAXWATCH)
    Isupport.add("WATCHOPTS", "A")
    Command.add(module, cmd_watch, "WATCH", 1)
