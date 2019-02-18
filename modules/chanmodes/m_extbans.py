#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
man, I don't know
"""

import ircd
import time
import os
import sys
from threading import Timer

from modules.m_mode import makeMask

from handle.functions import _print, match

rt = None

ext_bans = 'TtCO'

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

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.daemon = True
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False

from modules.m_joinpart import checkMatch

def init(self):
    global rt
    rt = RepeatedTimer(1, checkExpiredBans, self) # it auto-starts, no need of rt.start()

def unload(self):
    global rt
    rt.stop()

@ircd.Modules.support(('EXTBAN=~,'+str(ext_bans), True)) ### (support string, boolean if support must be sent to other servers)
@ircd.Modules.events('mode')
#def extbans(self, localServer, recv, tmodes=None, param=None):
def extbans(*args): ### Params: self, localServer, recv, tmodes, param, commandQueue
    if len(args) < 5:
        return
    try:
        self = args[0]
        localServer = args[1]
        recv = args[2]
        tmodes = args[3]
        param = args[4]
        commandQueue = args[5]
        channel = channel = list(filter(lambda c: c.name.lower() == recv[0].lower(), localServer.channels))
        if not channel:
            return
        channel = channel[0]
        paramcount = 0
        action = ''

        for m in recv[1]:
            #print('m: {}'.format(m))
            #print('paramcount: {}'.format(paramcount))
            if m in '+-':
                action = m
                continue
            if m in localServer.channel_modes[3]:
                continue
            try:
                rawParam = recv[2:][paramcount]
            except:
                paramcount += 1
                continue
            try:
                rawParam.split(':')[1][0]
            except:
                paramcount += 1
                continue
            if rawParam[0] != '~':
                paramcount += 1
                continue
            if rawParam[1] not in ext_bans:
                paramcount += 1
                continue


            if m == 'b':
                try:
                    setter = self.fullmask()
                except:
                    setter = self.hostname
                if action != '+' or rawParam in channel.bans:
                    paramcount += 1
                    continue
                if len(channel.bans) >= localServer.maxlist[m] and type(self).__name__ == 'User':
                    self.sendraw(478, '{} {} :Channel ban list is full'.format(channel.name, rawParam))
                    paramcount += 1
                    continue
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
                    ### Channel block.
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
                try:
                    setter = self.fullmask()
                except:
                    setter = self.hostname
                if action != '+' or rawParam in channel.bans:
                    paramcount += 1
                    continue
                if len(channel.bans) >= localServer.maxlist[m] and type(self).__name__ == 'User':
                    self.sendraw(478, '{} {} :Channel invex list is full'.format(channel.name, rawParam))
                    paramcount += 1
                    continue

                if rawParam[:2] == '~O':
                    ### Only allow specific oper classes.
                    if len(rawParam.split(':')) < 2:
                        paramcount += 1
                        continue

            c = None
            if m == 'b':
                c = channel.bans
            elif m == 'I':
                c = channel.invex
            if c:
                paramcount += 1
                tmodes.append(m)
                param.append(rawParam)
                c[rawParam] = {}
                c[rawParam]['setter'] = setter
                c[rawParam]['ctime'] = int(time.time())

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

@ircd.Modules.events('join')
def join(self, localServer, channel):
    try:
        overrides = []
        invite_override = False
        if self in channel.invites:
            invite_override = channel.invites[self]['override']
        for c in self.channels:
            ### First we check if the user is on a channel that's in the joined channel's banlist.
            for b in [b for b in channel.bans if b[:2] == '~C']:
                banChan = b.split(':')[1]
                ison_banchan = [chan for chan in localServer.channels if chan.name.lower() == banChan.lower() and self in chan.users]
                if (banChan.lower() == channel.name.lower() or ison_banchan) and not invite_override and not checkMatch(self, localServer, 'e', channel):
                    self.sendraw(474, '{} :Cannot join channel (+b1)'.format(channel.name))
                    return (False, None, overrides)

            for b in [b for b in c.bans if b[:2] == '~C']:
                banChan = b.split(':')[1]
                ison_banchan = [chan for chan in localServer.channels if chan.name.lower() == banChan.lower() and self in chan.users]
                if (banChan.lower() == channel.name.lower() or ison_banchan) and not invite_override and not checkMatch(self, localServer, 'e', channel):
                    self.sendraw(474, '{} :Cannot join channel (+b2)'.format(channel.name))
                    return (False, None, overrides)

        ### Now we check oper-class invex.
        for i in channel.invex:
            if i.startswith('~O'):
                oper_class = i.split(':')[1]
                if 'i' in channel.modes and ('o' in self.modes and (hasattr(self, 'operclass') and match(oper_class, self.operclass))) and 'i' not in overrides:
                    overrides.append('i')

        return (True, None, overrides)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
