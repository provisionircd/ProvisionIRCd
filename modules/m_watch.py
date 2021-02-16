"""
/watch command
"""

import time

import ircd
from handle.functions import logging

MAXWATCH = 256


class Watch(ircd.Command):
    """
    Maintain your WATCH list. You will be notified when a nickname on your WATCH list
    connects or disconnects, even if you don't share a channel.
    Your watchlist will be cleared when you disconnect.
    -
    Add a nickname:             /WATCH +nickname
    Remove a nickname:          /WATCH -nickname
    View current online users:  /WATCH
    """

    def __init__(self):
        self.command = 'watch'
        self.support = [('WATCH', MAXWATCH), ('WATCHOPTS', 'A')]

    def execute(self, client, recv, override=False, s_sync=True):
        if int(time.time()) - client.signon < 10:
            client.flood_safe = True
        else:
            client.flood_penalty += 100000
        try:
            watch_lower = [x.lower() for x in client.watchlist]
            if len(recv) == 1:
                watch_online = [user for user in self.ircd.users if user.registered and user.nickname.lower() in watch_lower]
                for user in watch_online:
                    client.sendraw(604, '{} {} {} {} :is online'.format(user.nickname, user.ident, user.cloakhost, user.signon))
                client.sendraw(607, ':End of WATCH l')
                return
            else:
                process_entries = recv[1:]
                for entry in process_entries:
                    if entry[0] not in '+-':
                        if entry == 'C':
                            client.watchC = True
                            if len(recv) == 2:  # Clear.
                                client.watchlist = []
                                logging.debug('Watchlist of {} cleared.'.format(client))
                        elif entry == 'S':
                            client.watchC = False
                            client.watchS = True
                        continue
                    nick = entry[1:]
                    if entry[0] == '+':
                        if len(client.watchlist) >= self.ircd.maxwatch:
                            return client.sendraw(512, 'Maximum size of WATCH-list is {} entries'.format(self.ircd.maxwatch))

                        if nick.lower() not in watch_lower:
                            client.watchlist.append(nick)
                        if not client.watchC and not client.watchS:
                            user = [user for user in self.ircd.users if user.nickname.lower() == nick.lower() and user.registered]
                            if user:
                                user = user[0]
                                client.sendraw(604, '{} {} {} {} :is online'.format(user.nickname, user.ident, user.cloakhost, user.signon))
                            else:
                                client.sendraw(605, '{} * * 0 :is offline'.format(nick))

                    elif entry[0] == '-':
                        if nick.lower() in watch_lower:
                            list_entry = [entry for entry in client.watchlist if entry.lower() == nick.lower()]
                            list_entry = list_entry[0]
                            client.watchlist.remove(list_entry)
                            if not client.watchC and not client.watchS:
                                is_online = [user for user in self.ircd.users if user.nickname.lower() == nick.lower()]
                                ident = '*' if not is_online else is_online[0].ident
                                cloakhost = '*' if not is_online else is_online[0].cloakhost
                                signon = '0' if not is_online else is_online[0].signon
                                client.sendraw(602, '{} {} {} {} :stopped watching'.format(list_entry, ident, cloakhost, signon))

                if client.watchS and not client.watchC:
                    for nick in client.watchlist:
                        user = [user for user in self.ircd.users if user.nickname.lower() == nick.lower() and user.registered]
                        if user:
                            user = user[0]
                            client.sendraw(604, '{} {} {} {} :is online'.format(user.nickname, user.ident, user.cloakhost, user.signon))
                        else:
                            client.sendraw(605, '{} * * 0 :is offline'.format(nick))
                    client.sendraw(603, ':You have {} and are on 0 WATCH entries'.format(len(client.watchlist)))
                    client.sendraw(606, ':{}'.format(' '.join(client.watchlist)))
                    client.sendraw(607, ':End of WATCH S')
                    client.watchS = False

        except Exception as ex:
            logging.exception(ex)


def init(ircd, reload=False):
    ircd.maxwatch = MAXWATCH
