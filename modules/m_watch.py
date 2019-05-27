#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/watch command
"""

import ircd
import time
import os
import sys

from handle.functions import _print

maxwatch = 256
def init(localServer, reload=False):
    localServer.maxwatch = maxwatch

@ircd.Modules.support('WATCH='+str(maxwatch))
@ircd.Modules.support('WATCHOPTS=A')
@ircd.Modules.commands('watch')
def watch(self, localServer, recv):
    if int(time.time()) - self.signon < 10:
        self.flood_safe = True
    self.flood_penalty += 100000
    try:
        watch_lower = [x.lower() for x in self.watchlist]
        if len(recv) == 1:
            watch_online = [user for user in localServer.users if user.registered and user.nickname.lower() in watch_lower]
            for user in watch_online:
                self.sendraw(604, '{} {} {} {} :is online'.format(user.nickname, user.ident, user.cloakhost, user.signon))
            self.sendraw(607, ':End of WATCH l')
            return
        else:
            process_entries = recv[1:]
            total_entries = []
            for entry in process_entries:
                if entry[0] not in '+-':
                    if entry == 'C':
                        self.watchC = True
                    elif entry == 'S':
                        self.watchC = False
                        self.watchS = True
                    continue
                nick = entry[1:]
                if entry[0] == '+':
                    if len(self.watchlist) >= localServer.maxwatch:
                        continue

                    if nick.lower() not in watch_lower:
                        self.watchlist.append(nick)
                    if not self.watchC and not self.watchS:
                        user = [user for user in localServer.users if user.nickname.lower() == nick.lower() and user.registered]
                        if user:
                            user = user[0]
                            self.sendraw(604, '{} {} {} {} :is online'.format(user.nickname, user.ident, user.cloakhost, user.signon))
                        else:
                            self.sendraw(605, '{} * * 0 :is offline'.format(nick))

                elif entry[0] == '-':
                    if nick.lower() in watch_lower:
                        list_entry = [entry for entry in self.watchlist if entry.lower() == nick.lower()]
                        list_entry = list_entry[0]
                        self.watchlist.remove(list_entry)
                        if not self.watchC and not self.watchS:
                            is_online = [user for user in localServer.users if user.nickname.lower() == nick.lower()]
                            ident = '*' if not is_online else is_online[0].ident
                            cloakhost = '*' if not is_online else is_online[0].cloakhost
                            signon = '0' if not is_online else is_online[0].signon
                            self.sendraw(602, '{} {} {} {} :stopped watching'.format(list_entry, ident, cloakhost, signon))

            if self.watchS and not self.watchC:
                for nick in self.watchlist:
                    user = [user for user in localServer.users if user.nickname.lower() == nick.lower() and user.registered]
                    if user:
                        user = user[0]
                        self.sendraw(604, '{} {} {} {} :is online'.format(user.nickname, user.ident, user.cloakhost, user.signon))
                    else:
                        self.sendraw(605, '{} * * 0 :is offline'.format(nick))
                self.sendraw(603, ':You have {} and are on 0 WATCH entries'.format(len(self.watchlist)))
                self.sendraw(606, ':{}'.format(' '.join(self.watchlist)))
                self.sendraw(607, ':End of WATCH S')
                self.watchS = False

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
