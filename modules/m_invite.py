#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/invite command
"""

import ircd
from handle.functions import _print
from modules.m_joinpart import checkMatch
import time

@ircd.Modules.params(2)
### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes('i', 3, 2, 'You need to be invited to join the channel', None, None) ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.support(('INVEX', 1))
@ircd.Modules.commands('invite')
def invite(self, localServer, recv, override=False):
    try:
        if type(self).__name__ == 'Server':
            override = True
            sourceServer = self

            self = list(filter(lambda u: u.uid == recv[0][1:], localServer.users))[0]
            recv = recv[1:]
        else:
            sourceServer = self.server

        oper_override = False

        user = list(filter(lambda u: u.nickname.lower() == recv[1].lower() or u.uid.lower() == recv[1].lower(), localServer.users))

        if not user:
            return self.sendraw(401, '{} :No such nick'.format(recv[1]))

        user = user[0]

        channel = list(filter(lambda c: c.name.lower() == recv[2].lower(), localServer.channels))

        if not channel:
            return self.sendraw(401, '{} :No such channel'.format(recv[2]))

        channel = channel[0]

        if self not in channel.users:
            if not override and not self.ocheck('o', 'override'):
                return self.sendraw(401, '{} :You are not on that channel'.format(channel.name))
            else:
                oper_override = True

        if self.chlevel(channel) < 3:
            if not self.ocheck('o', 'override'):
                return self.sendraw(482, '{} :You are not a channel half-operator'.format(channel.name))
            else:
                oper_override = True

        if 'V' in channel.modes:
            if not self.ocheck('o', 'override'):
                return self.sendraw(518, ':Invite is disabled on channel {} (+V)'.format(channel.name))
            else:
                oper_override = True

        if user in channel.users:
            return self.sendraw(443, '{} :is already on channel {}'.format(user.nickname, channel.name))

        if user in channel.invites and not self.ocheck('o', 'override'):
            return self.sendraw(342, '{} :has already been invited to {}'.format(user.nickname, channel.name))

        channel.invites[user] = {}
        ### All invites expire after 1 day.
        channel.invites[user]['ctime'] = int(time.time())
        channel.invites[user]['override'] = True if (self.ocheck('o', 'override') or self.chlevel(channel) >= 3) else False
        if oper_override:
            s = ''
            if checkMatch(user, localServer, 'b', channel):
                s = ' [Overriding +b]'
            elif 'i' in channel.modes:
                s = ' [Overriding +i]'
            elif 'l' in channel.modes and len(channel.users) >= channel.limit:
                s = ' [Overriding +l]'
            elif 'k' in channel.modes:
                s = ' [Overriding +k]'
            elif 'R' in channel.modes and 'r' not in user.modes:
                s = ' [Overriding +R]'
            elif 'z' in channel.modes and 'z' not in user.modes:
                s = ' [Overriding +z]'
            localServer.snotice('s', '*** OperOverride by {} ({}@{}) with INVITE {} {}{}'.format(self.nickname, self.ident, self.hostname, user.nickname, channel.name, s))

        self.broadcast([user], 'INVITE {} {}'.format(user.nickname, channel.name))

        self.sendraw(341, '{} {}'.format(user.nickname, channel.name))

        data = ':{} INVITE {} {}'.format(self.uid, user.nickname, channel.name)

        p = {'s_sync': False}
        localServer.handle('NOTICE', '{} :{} ({}@{}) invited {} to join the channel'.format(channel.name, self.nickname, self.ident, self.hostname, user.nickname), params=p)

        localServer.new_sync(localServer, sourceServer, data)
    except Exception as ex:
        _print(ex, server=localServer)
