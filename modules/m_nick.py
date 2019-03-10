#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/nick command
"""

import ircd

import time
import sys
import os
from handle.functions import match, logging

nicklen = 33

def init(localServer):
    localServer.nickflood = {}
    localServer.nicklen = nicklen

@ircd.Modules.support('NICKLEN='+str(nicklen))
@ircd.Modules.commands('nick')
def cmdnick(self, localServer, recv, override=False, sanick=False):
    try:
        if type(self).__name__ == 'Server':
            sourceServer = self
            override = True
            _self = self
            self = list(filter(lambda u: u.uid == recv[0][1:], localServer.users))
            if not self:
                _self.quit('This port is for servers only', error=True)
                return
            ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
            self = self[0]
            recv = recv[1:]
            hook = 'remote_nickchange'
        else:
            sourceServer = localServer
            hook = 'local_nickchange'

        if len(recv) < 2:
            return self.sendraw(431, ':No nickname given')

        nick = str(recv[1]).strip()
        if not override:
            nick = str(recv[1][:int(nicklen)]).strip()

        if nick.strip() == '':
            return self.sendraw(431, ':No nickname given')

        if nick[0].isdigit():
            return self.sendraw(432, '{} :Erroneous nickname (Invalid: {})'.format(nick, nick[0]))

        valid = 'abcdefghijklmnopqrstuvwxyz0123456789`^-_[]{}|\\'
        for c in nick:
            if c.lower() not in valid and not override:
                return self.sendraw(432, '{} :Erroneous nickname (Invalid: {})'.format(nick, c))

        if sanick:
            override = True

        if self in localServer.nickflood and len(localServer.nickflood[self]) >= int(localServer.conf['settings']['nickflood'].split(':')[0]) and not 'o' not in self.modes and not override:
            self.flood_penalty += 100000
            return self.sendraw(438, '{} :Nick change too fast. Please wait a while before attempting again.'.format(nick))


        inUse =  list(filter(lambda u: u.nickname.lower() == nick.lower(), localServer.users))
        if inUse and nick == self.nickname:
            ### Exact nick.
            return

        if inUse and nick.lower() != self.nickname.lower():
            return self.sendraw(433, '{} :Nickname is already in use'.format(nick))

        if 'Q' in localServer.tkl and not override:
            for entry in [entry for entry in localServer.tkl['Q'] if entry != '*']:
                if match(entry.split('@')[1].lower(), nick.lower()):
                    self.sendraw(432, '{} :Erroneous nickname ({})'.format(nick, localServer.tkl['Q'][entry]['reason']))
                    msg = '*** Q:Line Rejection -- Forbidden nick {} from client {} {}'.format(nick, self.ip, '[Current nick: {}]'.format(self.nickname) if self.nickname != '*' else '')
                    localServer.snotice('Q', msg)
                    return

        users = [self]
        for channel in self.channels:
            if 'N' in channel.modes and self.chlevel(channel) < 5 and not self.ocheck('o', 'override') and not override:
                return self.sendraw(447, ':{} Nick changes are not allowed on this channel'.format(channel.name))

            for user in channel.users:
                if user not in users and user != self:
                    users.append(user)

        if self.registered:
            if self not in localServer.nickflood:
                localServer.nickflood[self] = {}
            localServer.nickflood[self][time.time()] = True
            if self.server == localServer and not sanick:
                msg = '*** {} ({}@{}) has changed their nickname to {}'.format(self.nickname, self.ident, self.hostname, nick)
                self.server.snotice('N', msg)

            if sanick and type(sanick).__name__ == 'User':
                snomsg = '*** {} ({}@{}) used SANICK to change nickname {} to {}'.format(sanick.nickname, sanick.ident, sanick.hostname, self.nickname, nick)
                localServer.snotice('S', snomsg)

                msg = '*** Your nick has been forcefully changed by  {}.'.format(sanick.nickname)
                localServer.handle('NOTICE', '{} :{}'.format(self.nickname, msg))

            self.broadcast(users, 'NICK :{}'.format(nick))
            localServer.new_sync(localServer, sourceServer, ':{} NICK {} {}'.format(self.uid, nick, int(time.time())))

            watch_notify_offline = [user for user in localServer.users if self.nickname.lower() in [x.lower() for x in user.watchlist]]
            watch_notify_online = [user for user in localServer.users if nick.lower() in [x.lower() for x in user.watchlist]]
            for user in watch_notify_offline:
                user.sendraw(601, '{} {} {} {} :logged offline'.format(self.nickname, self.ident, self.cloakhost, self.signon))
            for user in watch_notify_online:
                user.sendraw(600, '{} {} {} {} :logged online'.format(nick, self.ident, self.cloakhost, self.signon))

            for callable in [callable for callable in localServer.hooks if callable[0].lower() == hook]:
                try:
                    callable[2](self, localServer)
                except Exception as ex:
                    logging.exception(ex)

        old = self.nickname
        self.nickname = nick

        if old == '*' and self.ident != '' and self.validping and (self.cap_end or not self.sends_cap):
            self.welcome()

    except Exception as ex:
        logging.exception(ex)
