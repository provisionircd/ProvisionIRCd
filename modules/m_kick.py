#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/kick command
"""

import ircd
import os
import sys

from handle.functions import _print

kicklen = 307

@ircd.Modules.params(2)
@ircd.Modules.support('KICKLEN='+str(kicklen))
@ircd.Modules.commands('kick')
def kick(self, localServer, recv, override=False, sync=True):
    try:
        oper_override = False
        if type(self).__name__ == 'Server':
            hook = 'remote_kick'
            override = True
            sourceServer = self
            S = recv[0][1:]
            source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
            self = source[0]
            recv = recv[1:]
            if type(self).__name__ == 'User':
                sourceID = self.uid
            else:
                sourceID = self.sid
        else:
            hook = 'local_kick'
            sourceServer = self.server
            sourceID = self.uid

        chan = recv[1]

        channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))

        if not channel:
            return self.sendraw(401, '{} :No such channel'.format(chan))

        channel = channel[0]

        if type(self).__name__ != 'Server':
            if self.chlevel(channel) < 2 and not self.ocheck('o', 'override') and not override:
                return self.sendraw(482, '{} :You\'re not a channel operator'.format(channel.name))

            elif self.chlevel(channel) < 2:
                oper_override = True
        # Set the userclass of the target.
        user = list(filter(lambda u: (u.nickname.lower() == recv[2].lower() or u.uid.lower() == recv[2].lower()) and '^' not in u.modes, localServer.users))

        if not user:
            self.sendraw(401, '{} :No such nick'.format(recv[2]))
            return

        user = user[0]

        if channel not in user.channels:
            return self.sendraw(441, '{} :User {} isn\'t on that channel'.format(channel.name, user.nickname))

        if (user.chlevel(channel) > self.chlevel(channel) or 'q' in user.modes) and not self.ocheck('o', 'override') and not override:
            return self.sendraw(972, '{} :You cannot kick {}{}'.format(channel.name, user.nickname,' (+q)' if 'q' in user.modes else ''))

        elif user.chlevel(channel) > self.chlevel(channel) or 'q' in user.modes:
            oper_override = True

        if 'Q' in channel.modes and self.chlevel(channel) < 5 and not self.ocheck('o', 'override') and not override:
            return self.sendraw(404, '{} :KICKs are not permitted in this channel'.format(channel.name))

        elif 'Q' in channel.modes and self.chlevel(channel) < 5 and not override:
            oper_override = True
        if len(recv) == 3:
            reason = self.nickname
        else:
            reason = ' '.join(recv[3:])
        if reason[0] == ':':
            reason = reason[1:]
        reason = reason[:kicklen]
        success = True
        for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'pre_local_kick']:
            try:
                success = callable[2](self, localServer, user, channel, reason)
                if not success:
                    break
            except Exception as ex:
                _print('Exception in module {}: {}'.format(callable[2], ex), server=localServer)
        if not success:
            return

        if oper_override:
            self.server.snotice('s', '*** OperOverride by {} ({}@{}) with KICK {} {} ({})'.format(self.nickname, self.ident, self.hostname, channel.name, user.nickname, reason))
        self.broadcast(channel.users, 'KICK {} {} :{}'.format(channel.name, user.nickname, reason))
        user.channels.remove(channel)
        channel.users.remove(user)
        channel.usermodes.pop(user)

        if len(channel.users) == 0 and 'P' not in channel.modes:
            localServer.channels.remove(channel)

        for callable in [callable for callable in localServer.events if callable[0].lower() == hook]:
            try:
                success = callable[1](self, localServer, user, channel, reason)
                if not success:
                    break
            except Exception as ex:
                _print('Exception in module {}: {}'.format(callable[2], ex), server=localServer)
        if not success:
            return

        if sync:
            localServer.new_sync(localServer, sourceServer, ':{} KICK {} {} :{}'.format(sourceID, channel.name, user.nickname, reason))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
