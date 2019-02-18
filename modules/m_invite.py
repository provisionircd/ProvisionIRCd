#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/invite command
"""

import ircd
from handle.functions import _print
import time

@ircd.Modules.params(2)
@ircd.Modules.commands('invite')
def invite(self, localServer, recv, override=False):
    try:
        ### This should be at the start of every command, where source = where the commsnd came from.
        if type(self).__name__ == 'Server':
            override = True
            originServer = self

            self = list(filter(lambda u: u.uid == recv[0][1:], localServer.users))[0]
            recv = recv[1:]

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
            localServer.snotice('s', '*** OperOverride by {} ({}@{}) with INVITE {} {}'.format(self.nickname, self.ident, self.hostname, user.nickname, channel.name))

        self.broadcast([user], 'INVITE {} {}'.format(user.nickname, channel.name))

        self.sendraw(341, '{} {}'.format(user.nickname, channel.name))

        ### Old token: *
        data = ':{} INVITE {} {}'.format(self.uid, user.nickname, channel.name)

        #for u in [u for u in channel.users if u.chlevel(channel) >= 3]:
        localServer.handle('NOTICE', '{} :{} ({}@{}) invited {} to join the channel'.format(channel.name, self.nickname, self.ident, self.hostname, user.nickname))

        localServer.syncToServers(localServer, self.server, data)
    except Exception as ex:
        _print(ex, server=localServer)
