#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
commands /join and /part
"""

import ircd

Channel = ircd.Channel

from handle.functions import match, _print
import time
import re
import os
import sys

chantypes = '#+&'
chanlen = 33

def init(localServer):
    ### Other modules also require this information, like /privmsg and /notice
    localServer.chantypes = chantypes

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
R2 = '\033[91m' # bright red
G = '\033[32m' # green
G2 = '\033[92m' # bright green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

def checkMatch(self, localServer, type, channel):
    if type == 'b':
        for b in channel.bans:
            if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
                return True
            if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
                return True
            if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
                return True
    if type == 'e':
        for e in channel.excepts:
            if (match(e, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
                return True
            if (match(e, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
                return True
            if (match(e, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
                return True

    if type == 'I':
        for I in channel.invex:
            if (match(I, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
                return True
            if (match(I, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
                return True
            if (match(I, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
                return True


@ircd.Modules.params(1)
@ircd.Modules.support('CHANTYPES='+str(chantypes))
@ircd.Modules.support('CHANNELLEN='+str(chanlen))
@ircd.Modules.commands('join')
def join(self, localServer, recv, override=False, skipmod=None, sourceServer=None):
    try:
        """Syntax: /JOIN <channel> [key]
        Joins a given channel with optional [key]."""
        hook = 'local_join'
        if type(self).__name__ == 'Server':
            if not sourceServer:
                sourceServer = self
            S = recv[0][1:]
            #source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
            #self = source[0]
            recv = recv[1:]
            override = True
            hook = 'remote_join'
        elif not sourceServer:
            sourceServer = self.server

        if recv[1] == '0':
            for channel in list(self.channels):
                self.handle('PART {} :Left all channels'.format(channel.name))
            return

        pc = 0
        key = None
        for chan in recv[1].split(','):
            regex = re.compile('\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?', re.UNICODE)
            chan = regex.sub('', chan).strip()
            channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))
            if channel and channel[0] in self.channels or not chan:
                continue

            if len(chan) == 1 and not override:
                continue

            continueLoop = False
            valid = "abcdefghijklmnopqrstuvwxyz0123456789`~!@#$%^&*()-=_+[]{}\\|;':\"./<>?"

            for c in chan:
                if c.lower() not in valid and (sourceServer == localServer and not channel):
                    self.sendraw(479, '{} :Illegal channel name'.format(chan))
                    continueLoop = True
                    break
            if continueLoop:
                continue
            ### This key-check can be improved. Check which modes require params, and increase accordingly.
            if len(recv) > 2:
                try:
                    key = recv[2:][pc]
                    pc += 1
                except:
                    pass

            if chan[0] not in chantypes and recv[0] != '0' and (sourceServer == localServer and not channel):
                self.sendraw(403, '{} :Invalid channel name'.format(chan))
                continue

            if len(chan) > chanlen and (sourceServer == localServer and not channel):
                self.sendraw(485, '{} :Channel too long'.format(chan))
                continue

            if not channel:
                new = Channel(chan)
                localServer.channels.append(new)
                channel = [new]
            channel = channel[0]

            invite_override = False
            if self in channel.invites:
                invite_override = channel.invites[self]['override']

            success = True
            broadcastjoin = None
            overrides = []
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'pre_'+hook and callable[3] != skipmod]:
                try:
                    success, temp_broadcastjoin, overrides = callable[2](self, localServer, channel)
                    if type(temp_broadcastjoin) == list and broadcastjoin is None:
                        broadcastjoin = temp_broadcastjoin
                    if not success:
                        break
                except Exception as ex:
                    _print('Exception in {}: {}'.format(callable[2], ex), server=localServer)
            if not success:
                continue
            if not override:
                if 'O' in channel.modes and 'o' not in self.modes:
                    self.sendraw(520, '{} :Cannot join channel (IRCops only)'.format(channel.name))
                    continue

                if 'R' in channel.modes and 'r' not in self.modes and not invite_override:
                    self.sendraw(477, '{} :You need a registered nick to join that channel'.format(channel.name))
                    continue

                if 'z' in channel.modes and 'z' not in self.modes and not invite_override:
                    self.sendraw(489, '{} :Cannot join channel (not using a secure connection)'.format(channel.name))
                    continue

                if checkMatch(self, localServer, 'b', channel) and not checkMatch(self, localServer, 'e', channel) and not invite_override and 'b' not in overrides:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    continue

                if channel.limit != 0 and len(channel.users) >= channel.limit and not invite_override:
                    if channel.redirect:
                        self.handle('JOIN', channel.redirect)
                        self.sendraw(471, '{} :Channel is full so you are redirected to {}'.format(channel.name, channel.redirect))
                        continue

                    self.sendraw(471, '{} :Cannot join channel (+l)'.format(channel.name))
                    continue

                if channel.key and key != channel.key and not invite_override:
                    ### Check key based on modes that require params.
                    self.sendraw(475, '{} :Cannot join channel (+k)'.format(channel.name))
                    continue

                if 'i' in channel.modes and self not in channel.invites and not checkMatch(self, localServer, 'I', channel) and not invite_override and 'i' not in overrides:
                    self.sendraw(473, '{} :Cannot join channel (+i)'.format(channel.name))
                    continue

            if not channel.users and (self.server.eos or self.server == localServer) and channel.name[0] != '+':
                channel.usermodes[self] = 'o'
            else:
                channel.usermodes[self] = ''

            if type(broadcastjoin) != list:
                broadcastjoin = channel.users+[self]

            channel.users.append(self)
            self.channels.append(channel)
            if self in channel.invites:
                del channel.invites[self]

            for user in broadcastjoin:
                data = ':{}!{}@{} JOIN {}{}'.format(self.nickname, self.ident, self.cloakhost, channel.name, ' {} :{}'.format(self.svid, self.realname) if 'extended-join' in user.caplist else '')
                user._send(':{}!{}@{} JOIN {}{}'.format(self.nickname, self.ident, self.cloakhost, channel.name, ' {} :{}'.format(self.svid, self.realname) if 'extended-join' in user.caplist else ''))

            if channel.topic_time != 0:
                self.handle('TOPIC', channel.name)
            self.handle('NAMES', channel.name)

            prefix = ''
            for mode in [mode for mode in localServer.chprefix if mode in channel.usermodes[self]]:
                prefix += localServer.chprefix[mode]

            if channel.name[0] != '&' and broadcastjoin and (sourceServer.eos or sourceServer == localServer):
                data = ':{} SJOIN {} {}{} :{}{}'.format(sourceServer.sid, channel.creation, channel.name, ' +{}'.format(channel.modes) if channel.modes and channel.users == [self] else '', prefix, self.uid)
                localServer.new_sync(localServer, sourceServer, data)

            if channel.users == [self] and channel.name[0] != '+':
                sourceServer.handle('MODE', '{} +nt'.format(channel.name))

            ### Check for module events (after join)
            success = True
            broadcastjoin = channel.users+[self]
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == hook and callable[3] != skipmod]:
                try:
                    callable[2](self, localServer, channel)
                except Exception as ex:
                    _print('Exception in {}: {}'.format(callable[2], ex), server=localServer)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

@ircd.Modules.params(1)
@ircd.Modules.commands('part')
def part(self, localServer, recv, reason=None):
    try:
        if type(self).__name__ == 'Server':
            hook = 'remote_part'
            sourceServer = self
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
            recv = recv[1:]
        else:
            hook = 'local_part'
            sourceServer = self.server

        if not reason:
            if len(recv) > 2:
                reason = ' '.join(recv[2:])
                if reason.startswith(':'):
                    reason = reason[1:]
                reason = ':{}'.format(reason)
            else:
                reason = ''

            reason = reason.rstrip()

        if 'static-part' in localServer.conf['settings'] and localServer.conf['settings']['static-part']:
            reason = localServer.conf['settings']['static-part']

        for chan in recv[1].split(','):
            channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))
            if not channel or self not in channel[0].users:
                self.sendraw(442, '{} :You\'re not on that channel'.format(chan))
                continue

            channel = channel[0]

            broadcastpart = channel.users+[self]
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'pre_'+hook]:
                try:
                    success, broadcastpart = callable[2](self, localServer, channel)
                except Exception as ex:
                    _print('Exception in module: {}: {}'.format(callable[2], ex), server=localServer)
                    _print(ex, server=localServer)

            self.channels.remove(channel)
            channel.usermodes.pop(self)
            channel.users.remove(self)
            if type(broadcastpart) != list:
                broadcastpart = channel.users+[self]
            if len(channel.users) == 0 and 'P' not in channel.modes:
                localServer.channels.remove(channel)

            self.broadcast(broadcastpart, 'PART {} {}'.format(channel.name, reason))

            broadcastpart = channel.users+[self]
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == hook]:
                try:
                    callable[2](self, localServer, channel)
                except Exception as ex:
                    _print(ex, server=localServer)

            if channel.name[0] != '&':
                localServer.new_sync(localServer, sourceServer, ':{} PART {} {}'.format(self.uid, channel.name, reason))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
