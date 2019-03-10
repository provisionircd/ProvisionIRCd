#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/privmsg and /notice commands
"""

import ircd

from handle.functions import match, checkSpamfilter, logging

import time
import os
import sys
import re

maxtargets = 20

@ircd.Modules.support('MAXTARGETS='+str(maxtargets))
@ircd.Modules.commands('privmsg', 'zegding')
def privmsg(self, localServer, recv, override=False, safe=False):
    try:
        if type(self).__name__ == 'Server':
            sourceServer = self
            override = True
            if self != localServer:
                S = recv[0][1:]
                source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
                self = source[0]
                sourceID = self.uid if type(self).__name__ == 'User' else self.sid
            recv = recv[1:]
            recv = localServer.parse_command(' '.join(recv[0:]))
        else:
            sourceServer = self.server
            sourceID = self.uid
            if self.ocheck('o', 'override'):
                override = True

        if len(recv) < 2:
            self.sendraw(411, ':No recipient given')
            return

        elif len(recv) < 3:
            self.sendraw(412, ':No text to send')
            return

        targets = recv[1].split(',')

        msg = ' '.join(recv[2:]).rstrip()

        if type(self).__name__ == 'User':
            self.flood_penalty += len(msg) * 100

        for target in targets[:maxtargets]:
            sync = True
            if target[0] not in localServer.chantypes:
                user = list(filter(lambda u: u.nickname.lower() == target.lower() or u.uid.lower() == target.lower(), localServer.users))

                if not user:
                    self.sendraw(401, '{} :No such nick'.format(target))
                    continue
                user = user[0]

                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, user.nickname, 'private', msg):
                    continue

                if user.server == localServer:
                    sync = False

                if type(self).__name__ == 'User':
                    for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'pre_usermsg']:
                        try:
                            msg = callable[2](self, localServer, user, msg)
                            if not msg:
                                break
                        except Exception as ex:
                            logging.exception(ex)
                    if not msg:
                        continue
                if user.away:
                    self.sendraw(301, '{} :{}'.format(user.nickname, user.away))

                if type(self).__name__ == 'User':
                    self.broadcast([user], 'PRIVMSG {} :{}'.format(user.nickname, msg))
                    self.idle = int(time.time())
                    if 'echo-message' in self.caplist:
                        self._send(':{} PRIVMSG {} :{}'.format(self.fullmask(), user.nickname, msg))
                    for callable in [callable for callable in localServer.events if callable[0].lower() == 'usermsg']:
                        try:
                            callable[2](self, localServer, user, msg)
                        except Exception as ex:
                            logging.exception(ex)

                if sync:
                    data = ':{} PRIVMSG {} :{}'.format(sourceID, user.nickname, msg)
                    localServer.new_sync(localServer, sourceServer, data)

            else:
                channel = [channel for channel in localServer.channels if channel.name.lower() == target.lower()]

                if not channel:
                    self.sendraw(401, '{} :No such channel'.format(target))
                    continue

                channel = channel[0]
                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, channel.name, 'channel', msg):
                    continue

                if not override:
                    if self not in channel.users and 'n' in channel.modes and not override:
                        self.sendraw(404, '{} :No external messages'.format(channel.name))
                        continue

                    if 'C' in channel.modes and (msg[0] == '' and msg[-1] == '') and msg.split()[0] != 'ACTION' and self.chlevel(channel) < 5 and not override:
                        self.sendraw(404, '{} :CTCPs are not permitted in this channel'.format(channel.name))
                        continue

                    if 'm' in channel.modes and self.chlevel(channel) == 0 and not override:
                        self.sendraw(404, '{} :Cannot send to channel (+m)'.format(channel.name))
                        continue

                if type(self).__name__ == 'User':
                    for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'pre_chanmsg']:
                        try:
                            msg = callable[2](self, localServer, channel, msg)
                            if not msg:
                                break
                        except Exception as ex:
                            logging.exception(ex)
                    if not msg:
                        continue

                users = [user for user in channel.users if user != self and 'd' not in user.modes]
                self.broadcast(users, 'PRIVMSG {} :{}'.format(channel.name, msg))
                if type(self).__name__ == 'User' and 'echo-message' in self.caplist and 'd' not in self.modes:
                    self._send(':{} PRIVMSG {} :{}'.format(self.fullmask(), channel.name, msg))

                self.idle = int(time.time())


                while len(channel.msg_backlog) >= 10:
                    channel.msg_backlog = channel.msg_backlog[1:]
                data = (self.fullmask(), time.time()*10, msg)
                channel.msg_backlog.append(data)

                if sync:
                    localServer.new_sync(localServer, sourceServer, ':{} PRIVMSG {} :{}'.format(sourceID, target, msg))

                ### Check for module hooks (channel messages).
                for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'chanmsg']:
                    try:
                        callable[2](self, localServer, channel, msg)
                    except Exception as ex:
                        logging.exception(ex)

    except Exception as ex:
        logging.exception(ex)


@ircd.Modules.commands('notice')
def notice(self, localServer, recv, override=False, s_sync=True):
    try:
        if type(self).__name__ == 'Server':
            sourceServer = self
            S = recv[0][1:]
            source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
            if not source:
                return
            self = source[0]
            sourceID = self.uid if type(self).__name__ == 'User' else self.sid
            recv = recv[1:]

            recv = localServer.parse_command(' '.join(recv[0:]))

        else:
            sourceServer = self.server
            sourceID = self.uid
            if self.ocheck('o', 'override'):
                override = True

        if len(recv) < 2:
            return self.sendraw(411, ':No recipient given')

        elif len(recv) < 3:
            return self.sendraw(412, ':No text to send')

        global msg
        msg = ' '.join(recv[2:])

        if type(self).__name__ == 'User':
            self.flood_penalty += len(msg) * 100

        for target in recv[1].split(',')[:maxtargets]:
            sync = True
            if target[0] == '$' and sourceServer != localServer:
                server = list(filter(lambda s: s.hostname.lower() == target[1:].lower(), localServer.servers+[localServer]))[0]
                if server == localServer:
                    for user in (user for user in localServer.users if user.server == server):
                        self.broadcast([user], 'NOTICE ${} :{}'.format(server.hostname.lower(), msg))
                else:
                    for s in (s for s in localServer.servers if s != sourceServer):
                        s._send(':{} NOTICE ${} :{}'.format(sourceID, server.hostname.lower(), msg))

            elif target[0] not in localServer.chantypes:
                user = list(filter(lambda u: u.nickname.lower() == target.lower() or u.uid.lower() == target.lower(), localServer.users))
                if not user:
                    self.sendraw(401, '{} :No such user'.format(target))
                    continue

                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, user[0].nickname, 'private', msg):
                    continue

                if user[0].server == localServer:
                    sync = False

                self.broadcast(user, 'NOTICE {} :{}'.format(user[0].nickname, msg))

                if sync:
                    localServer.new_sync(localServer, sourceServer, ':{} NOTICE {} :{}'.format(sourceID, target, msg))

                if type(self).__name__ == 'User':
                    self.idle = int(time.time())
            else:
                channel = list(filter(lambda c: c.name.lower() == target.lower(), localServer.channels))

                if not channel:
                    self.sendraw(401, '{} :No such channel'.format(target))
                    continue

                channel = channel[0]

                if self not in channel.users and 'n' in channel.modes and not override:
                    self.sendraw(404, '{} :No external messages'.format(channel.name))
                    continue

                if 'T' in channel.modes and self.chlevel(channel) < 5 and not override:
                    self.sendraw(404, '{} :NOTICEs are not permitted in this channel'.format(channel.name))
                    continue

                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, channel.name, 'channel', msg):
                    continue

                self.broadcast([user for user in channel.users], 'NOTICE {} :{}'.format(channel.name, msg))

                if type(self).__name__ == 'User':
                    self.idle = int(time.time())

                if sync and s_sync:
                    localServer.new_sync(localServer, sourceServer, ':{} NOTICE {} :{}'.format(sourceID, target, msg))

    except Exception as ex:
        logging.exception(ex)
