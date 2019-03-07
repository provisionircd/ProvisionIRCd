#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
support for extended bans
"""

import ircd
import time
import os
import sys
import re

from modules.m_mode import makeMask
from modules.m_joinpart import checkMatch

from handle.functions import match, logging

ext_bans = 'TtCOa'
prefix = '~'

def checkExtMatch(type, action, channel, msg):
    try:
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
    except Exception as ex:
        logging.exception(ex)

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

@ircd.Modules.hooks.loop()
def checkExpiredBans(localServer):
    remove_bans = {}
    for chan in localServer.channels:
        remove_bans[chan] = []
        for ban in [ban for ban in chan.bans if ban[:2] == '~t']:
            minutes = int(ban.split(':')[1]) * 60
            banset = int(chan.bans[ban]['ctime'])
            if int(time.time()) > (minutes + banset):
                remove_bans[chan].append(ban)
    for chan in remove_bans:
        if len(remove_bans[chan]) < 1:
            continue
        bans = ' '.join(remove_bans[chan])
        tmodes = 'b'*len(remove_bans[chan])
        localServer.handle('MODE', '{} -{} {} 0'.format(chan.name, tmodes, bans))

@ircd.Modules.support(('EXTBAN='+prefix+','+str(ext_bans), True)) ### (support string, boolean if support must be sent to other servers)
@ircd.Modules.hooks.pre_local_chanmode()
@ircd.Modules.hooks.pre_remote_chanmode()
def extbans(self, localServer, channel, modes, params, modebuf, parambuf):
    try:
        paramcount = 0
        action = ''

        for m in modes:
            if m in '+-':
                action = m
                continue
            try:
                rawParam = params[paramcount]
            except:
                paramcount += 1
                continue
            try:
                rawParam.split(':')[1][0]
            except:
                paramcount += 1
                continue
            if rawParam[0] != prefix:
                paramcount += 1
                continue
            if rawParam[1] not in ext_bans:
                paramcount += 1
                continue
            try:
                setter = self.fullmask()
            except:
                setter = self.hostname

            if m == 'b':
                if rawParam[:2] == '~T':
                    ### Text block.
                    if rawParam.split(':')[1] not in ['block', 'replace'] or len(rawParam.split(':')) < 3:
                        paramcount += 1
                        continue
                    bAction = rawParam.split(':')[1]
                    if not rawParam.split(':')[2:]:
                        paramcount += 1
                        continue
                    if bAction == 'replace':
                        ### Replace requires an additional parameter: ~T:replace:match:replacement
                        if len(rawParam.split(':')) < 4:
                            paramcount += 1
                            continue
                        if not rawParam.split(':')[3]:
                            paramcount += 1
                            continue
                elif rawParam[:2] == '~C':
                    ### Channel block.
                    if len(rawParam.split(':')) < 2:
                        paramcount += 1
                        continue
                    chanBan = rawParam.split(':')[1]
                    if chanBan[0] != '#':
                        paramcount += 1
                        continue
                    tempchan = list(filter(lambda c: c.name.lower() == chanBan.lower(), localServer.channels))
                    if tempchan and len(channel.users) > 2:
                        tempchan = tempchan[0]
                        ### tempchan users are forbidden on channel.
                        for user in [user for user in channel.users if tempchan in user.channels and user.chlevel(channel) < 2 and not user.ocheck('o', 'override') and not checkMatch(user, localServer, 'e', channel)]:
                            cmd = ('KICK', '{} {} :Users from {} are not welcome here'.format(channel.name, user.nickname, tempchan.name))
                            commandQueue.append(cmd)

                elif rawParam[:2] == '~t':
                    ### Timed bans.
                    if len(rawParam.split(':')) < 3:
                        paramcount += 1
                        continue
                    bTime = rawParam.split(':')[1]
                    if not bTime.isdigit():
                        paramcount += 1
                        continue
                    banmask = makeMask(localServer, rawParam.split(':')[2])
                    rawParam = '{}:{}'.format(':'.join(rawParam.split(':')[:2]), banmask)

            elif m == 'I':
                if rawParam[:2] == '~O':
                    if len(rawParam.split(':')) < 2:
                        paramcount += 1
                        continue

            c = None
            if m == 'b':
                c = channel.bans
            elif m == 'I':
                c = channel.invex
            elif m == 'e':
                c = channel.excepts
            if c is not None:
                paramcount += 1
                if action == '+' and rawParam not in c:
                    modebuf.append(m)
                    parambuf.append(rawParam)
                    c[rawParam] = {}
                    c[rawParam]['setter'] = setter
                    c[rawParam]['ctime'] = int(time.time())

    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.pre_local_join()
def join(self, localServer, channel):
    try:
        overrides = []
        invite_override = False
        if self in channel.invites:
            invite_override = channel.invites[self]['override']
        for c in self.channels:
            for b in [b for b in channel.bans if b[:2] == '~C']:
                banChan = b.split(':')[1]
                ison_banchan = [chan for chan in localServer.channels if chan.name.lower() == banChan.lower() and self in chan.users]
                if (banChan.lower() == channel.name.lower() or ison_banchan) and not invite_override and not checkMatch(self, localServer, 'e', channel):
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, None, overrides)

            for b in [b for b in c.bans if b[:2] == '~C']:
                banChan = b.split(':')[1]
                ison_banchan = [chan for chan in localServer.channels if chan.name.lower() == banChan.lower() and self in chan.users]
                if (banChan.lower() == channel.name.lower() or ison_banchan) and not invite_override and not checkMatch(self, localServer, 'e', channel):
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, None, overrides)

        for b in [b for b in channel.bans if b[:2] == '~t' and not invite_override and not checkMatch(self, localServer, 'e', channel)]:
            mask = b.split(':')[2]
            ban = 0
            if (match(mask, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
                ban = 1
            if (match(mask, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
                ban = 1
            if (match(mask, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
                ban = 1
            if ban:
                self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                return (False, None, overrides)

        for i in channel.invex:
            if i.startswith('~O'):
                oper_class = i.split(':')[1]
                if 'i' in channel.modes and ('o' in self.modes and (hasattr(self, 'operclass') and match(oper_class, self.operclass))) and 'i' not in overrides:
                    overrides.append('i')
            if i.startswith('~a'):
                account = i.split(':')[1]
                if 'i' in channel.modes and ('r' in self.modes and (hasattr(self, 'svid') and match(account, self.svid))) and 'b' not in overrides:
                    overrides.append('i')

        for e in channel.excepts:
            if e.startswith('~a'):
                account = e.split(':')[1]
                if ('r' in self.modes and (hasattr(self, 'svid') and match(account, self.svid))) and 'b' not in overrides:
                    overrides.append('b')

        for b in channel.bans:
            if b.startswith('~a'):
                account = b.split(':')[1]
                if ('r' in self.modes and (hasattr(self, 'svid') and match(account, self.svid))) and 'b' not in overrides:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, None, overrides)

        return (True, None, overrides)

    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.pre_chanmsg()
def pre_chanmsg(self, localServer, channel, msg):
    if checkExtMatch('b', 'block', channel, msg) and self.chlevel(channel) < 3 and not self.ocheck('o', 'override'):
        self.sendraw(404, '{} :Cannot send to channel (+b ~T)'.format(channel.name))
        return 0
    if checkExtMatch('b', 'replace', channel, msg) and self.chlevel(channel) < 5 and not self.ocheck('o', 'override'):
        msg = checkExtMatch('b', 'replace', channel, msg)
    return msg
