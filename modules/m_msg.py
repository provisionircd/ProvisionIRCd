#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/privmsg and /notice commands
"""

import ircd

from handle.functions import match, checkSpamfilter, _print

import time
import os
import sys
import re

msg = ''

maxtargets = 20

def char_repeat(string, char, amount):
    for word in [word for word in string.split(' ') if '://' not in word and 'www.' not in word]: ### Excluding urls.
        if char == '*':
            for c in 'abcdefghijklmnopqrstuwvwxyz,.?!1234567890:':
                if word.lower().count(c.lower()) >= int(amount):
                    return True
        else:
            if word.count(char.lower()) >= int(amount):
                return True
    return False

def checkMatch(self, type, action, channel, msg):
    if type == 'b':
        replaceDone, did_replace = False, False
        tempMsg = msg
        regex = re.compile('\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?', re.UNICODE)
        for ban in [ban for ban in channel.bans if ban[:2] == '~T' and ban.split(':')[1] == action]:
            m = ban.split(':', 2)[2]
            m = regex.sub('', m)
            rep_char_block = None
            try:
                int(ban.split(':')[3]) > 0
                rep_char_block = ban.split(':')[3]
            except:
                pass
            if action == 'block':
                char = m.split(':')[0]
                if rep_char_block and char_repeat(msg, char, rep_char_block):
                    return True
                block = match(m.lower(), msg.lower()) or m.lower() in msg.lower().split()
                if not rep_char_block and block:
                    return True
            if action == 'replace':
                ### This just works, so don't mess it up.
                m = ban.split(':', 2)[2]
                if m.startswith(':'):
                    search = ':'+m.split(':')[1]
                    replaceWith = m.split(':', 2)[2]
                else:
                    search = m.split(':')[0]
                    if m.split(':')[1] != '':
                        replaceWith = m.split(':')[1]
                    else:
                        replaceWith = ':'+m.split(':', 2)[2]
                for word in msg.split():
                    word = regex.sub('', word)
                    tempWord = word.lower()
                    if match(search.lower(),tempWord) or search.lower() == tempWord:
                        temp = search.replace('*', '')
                        if word.isupper():
                            temp = temp.upper()
                            did_replace = True
                            replaceWith = replaceWith.upper()
                        elif not word.islower():
                            temp = re.search(temp, word, flags=re.IGNORECASE).group()
                        did_replace = True
                        tempMsg = tempMsg.replace(temp, replaceWith)
                if did_replace:
                    replaceDone = True

        if replaceDone:
            return tempMsg

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

        if len(recv) < 2:
            self.sendraw(411, ':No recipient given')
            return

        elif len(recv) < 3:
            self.sendraw(412, ':No text to send')
            return

        targets = recv[1].split(',')

        global msg
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

                ### Check for module events (private messages).
                success = True
                if type(self).__name__ == 'User':
                    for callable in [callable for callable in localServer.events if callable[0].lower() == recv[0].lower()]:
                        try:
                            success = callable[1](self, localServer, user, msg, callable[2])
                            if not success:
                                break
                        except Exception as ex:
                            _print('Exception in {} :{}'.format(callable[2],ex), server=localServer)
                    if not success:
                        continue

                if user.away:
                    self.sendraw(301, '{} :{}'.format(user.nickname, user.away))

                self.broadcast([user], 'PRIVMSG {} :{}'.format(user.nickname, msg))
                self.idle = int(time.time())
                if 'echo-message' in self.caplist:
                    self._send(':{} PRIVMSG {} :{}'.format(self.fullmask(), user.nickname, msg))

                if sync:
                    localServer.new_sync(localServer, sourceServer, ':{} PRIVMSG {} :{}'.format(sourceID, user.nickname, msg))

            else:
                channel = [channel for channel in localServer.channels if channel.name.lower() == target.lower()]

                if not channel:
                    self.sendraw(401, '{} :No such channel'.format(target))
                    continue

                channel = channel[0]
                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, channel.name, 'channel', msg):
                    continue

                if not override:
                    if self not in channel.users and 'n' in channel.modes and not self.ocheck('o', 'override') and not override:
                        self.sendraw(404, '{} :No external messages'.format(channel.name))
                        continue

                    if 'C' in channel.modes and msg[0] == '' and msg[-1] == '' and self.chlevel(channel) < 4 and not self.ocheck('o', 'override') and not override:
                        self.sendraw(404, '{} :CTCPs are not permitted in this channel'.format(channel.name))
                        continue

                    if 'm' in channel.modes and self.chlevel(channel) == 0 and not self.ocheck('o', 'override') and not override:
                        self.sendraw(404, '{} :Cannot send to channel (+m)'.format(channel.name))
                        continue

                    if checkMatch(self, 'b', 'block', channel, msg) and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override:
                        self.sendraw(404, '{} :Cannot send to channel (+b ~T)'.format(channel.name))
                        continue

                    if checkMatch(self, 'b', 'replace', channel, msg) and self.chlevel(channel) < 4 and not self.ocheck('o', 'override') and not override:
                        msg = checkMatch(self, 'b', 'replace', channel, msg)

                if '^' in self.modes:
                    self.sendraw(404, '{} :You are invisible on channel {}'.format(channel.name, channel.name))
                    continue

                ### Check for module events (channel messages).
                success = True
                if type(self).__name__ == 'User':
                    for callable in [callable for callable in localServer.events if callable[0].lower() == recv[0].lower()]:
                        try:
                            success = callable[1](self, localServer, channel, msg, callable[2])
                            if not success:
                                break
                        except Exception as ex:
                            _print('Exception in {} :{}'.format(callable[2], ex), server=localServer)
                    if not success:
                        continue

                users = [user for user in channel.users if user != self]
                self.broadcast(users, 'PRIVMSG {} :{}'.format(channel.name, msg))
                if 'echo-message' in self.caplist:
                    self._send(':{} PRIVMSG {} :{}'.format(self.fullmask(), channel.name, msg))

                self.idle = int(time.time())

                if sync:
                    localServer.new_sync(localServer, sourceServer, ':{} PRIVMSG {} :{}'.format(sourceID, target, msg))

                ### Check for module events (channel messages).
                for callable in [callable for callable in localServer.events if callable[0].lower() == 'after_privmsg']:
                    try:
                        callable[1](self, localServer, channel, msg, callable[2])
                    except Exception as ex:
                        _print('Exception in {} :{}'.format(callable[2], ex), server=localServer)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)


@ircd.Modules.commands('notice')
def notice(self, localServer, recv, override=False):
    try:
        if type(self).__name__ == 'Server':
            sourceServer = self
            S = recv[0][1:]
            source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
            if not source:
                #print('ERROR: remote /notice source not found')
                return
            self = source[0]
            sourceID = self.uid if type(self).__name__ == 'User' else self.sid
            recv = recv[1:]

            recv = localServer.parse_command(' '.join(recv[0:]))

        else:
            sourceServer = self.server
            sourceID = self.uid

        if len(recv) < 2:
            return self.sendraw(411, ':No recipient given')

        elif len(recv) < 3:
            return self.sendraw(412, ':No text to send')

        targets = recv[1].split(',')

        global msg
        msg = ' '.join(recv[2:])

        if type(self).__name__ == 'User':
            self.flood_penalty += len(msg) * 100

        for target in targets[:maxtargets]:
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
                    #localServer.syncToServers(localServer, sourceServer, ':{} NOTICE {} :{}'.format(sourceID, target, msg))

                if type(self).__name__ == 'User':
                    self.idle = int(time.time())
            else:
                channel = list(filter(lambda c: c.name.lower() == target.lower(), localServer.channels))

                if not channel:
                    self.sendraw(401, '{} :No such channel'.format(target))
                    continue

                channel = channel[0]

                if self not in channel.users and 'n' in channel.modes and not self.ocheck('o', 'override') and not override:
                    self.sendraw(404, '{} :No external messages'.format(channel.name))
                    continue

                if 'T' in channel.modes and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override:
                    self.sendraw(404, '{} :NOTICEs are not permitted in this channel'.format(channel.name))
                    continue

                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, channel.name, 'channel', msg):
                    continue

                self.broadcast([user for user in channel.users], 'NOTICE {} :{}'.format(channel.name, msg))

                if type(self).__name__ == 'User':
                    self.idle = int(time.time())

                if sync:
                    localServer.new_sync(localServer, sourceServer, ':{} NOTICE {} :{}'.format(sourceID, target, msg))
                    #localServer.syncToServers(localServer, sourceServer, ':{} NOTICE {} :{}'.format(sourceID, target, msg))
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
