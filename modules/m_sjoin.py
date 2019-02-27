#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/sjoin command (server)
"""

import ircd
import re
import os
import sys

Channel = ircd.Channel

from modules.m_mode import processModes
from handle.functions import _print

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('sjoin')
def sjoin(self, localServer, recv):
    try:
        raw = ' '.join(recv)
        source = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], localServer.servers))
        if not source:
            return

        source = source[0]

        channel = recv[3]
        if channel[0] == '&':
            _print('{}ERROR: received a local channel from remote server: {}{}'.format(R, channel, W), server=localServer)
            self.squit('Sync error! Remote server tried to link local channels.')
            return

        if not self.eos:
            localServer.new_sync(localServer, self, raw)

        memberlist = ' '.join(' '.join(recv).split(':')[2:]).split('&')[0].split('"')[0].split("'")[0].split()

        banlist, excepts, invex = [], [], []
        try:
            banlist = ' '.join(recv).split('&')[1].split('"')[0].split()
        except:
            pass
        try:
            excepts = ' '.join(recv).split('"')[1].split("'")[0].split()
        except:
            pass
        try:
            invex = ' '.join(recv).split("'")[1].split()
        except:
            pass

        if recv[4].startswith('+'):
            modes = recv[4].replace('+','')
        else:
            modes = ''
        data = []

        giveModes = []
        giveParams = []

        removeModes = []
        removeParams = []

        timestamp = int(recv[2])

        localChan = None

        pc = 5
        for m in modes:
            if m == 'k':
                key = recv[pc]
                pc += 1
            if m == 'l':
                limit = recv[pc]
                pc += 1

        for member in memberlist:
            membernick = []
            for c in member:
                if c not in '*~@%+':
                    membernick.append(c)
            membernick = ''.join(membernick)

            userClass = list(filter(lambda c: c.nickname.lower() == membernick.lower() or c.uid == membernick, localServer.users))
            if not userClass:
                _print('{}ERROR: could not fetch userclass for remote user {}. Looks like the user did not sync correctly. Maybe nick collision, or remote leftover from a netsplit.{}'.format(R, membernick, W), server=localServer)
                continue

            userClass = userClass[0]
            p = {'override': True, 'sourceServer': self}
            userClass.handle('join', channel, params=p)
            localChan = list(filter(lambda c: c.name.lower() == channel.lower(), localServer.channels))[0]
            if len(localChan.users) == 1:
                ### Channel did not exist on localServer
                pass
            if userClass.server != localServer:
                _print('{}External user {} joined {} on local server.{}'.format(G, userClass.nickname, channel, W), server=localServer)
            if timestamp < localChan.creation and not source.eos:
                if '*' in member:
                    giveModes.append('q')
                    giveParams.append(userClass.nickname)
                if '~' in member:
                    giveModes.append('a')
                    giveParams.append(userClass.nickname)
                if '@' in member:
                    giveModes.append('o')
                    giveParams.append(userClass.nickname)
                if '%' in member:
                    giveModes.append('h')
                    giveParams.append(userClass.nickname)
                if '+' in member:
                    giveModes.append('v')
                    giveParams.append(userClass.nickname)

        if not localChan:
            return
        if timestamp < localChan.creation and not source.eos:
            finalModes = ' '.join(recv[3:]).split(':')[0].split()[0]
            for p in finalModes.split()[1:]:
                giveParams.append(p)

            # Remote channel is dominant. Replacing modes with remote channel
            # Clear the local modes.
            #
            _print('Remote channel {} is dominant. Replacing modes with remote channel'.format(channel), server=localServer)
            localChan.creation = timestamp
            if modes:
                for m in localChan.modes:
                    if m not in modes and m != 'k':
                        removeModes.append(m)
                        continue
                    if m == 'k' and key != localChan.key:
                        removeParams.append(localChan.key)
                        removeModes.append(m)
                    elif m == 'l' and limit != localChan.limit:
                        removeParams.append(localChan.limit)
                        removeModes.append(m)

                for m in modes:
                    if m not in localChan.modes:
                        giveModes.append(m)

            # Removing local channel user modes.
            for user in localChan.users:
                for m in localChan.usermodes[user]:
                    removeModes.append(m)
                    removeParams.append(user.nickname)

            for m in modes:
                if m == 'k':
                    giveParams.append(key)
                if m == 'limit':
                    giveParams.append(limit)

            for b in banlist:
                giveModes.append('b')
                giveParams.append(b)

            for e in excepts:
                giveModes.append('e')
                giveParams.append(e)

            for I in invex:
                giveModes.append('I')
                giveParams.append(I)

            data = []
            data.append(localChan.name)
            modes = '{}{}'.format('-'+''.join(removeModes) if removeModes else '', '+'+''.join(giveModes) if giveModes else '')
            data.append(modes)
            for p in removeParams:
                data.append(p)
            #if giveParams:
            #    data.append(':')
            for p in giveParams:
                data.append(p)

        elif timestamp == localChan.creation and not source.eos:
            if modes:
                _print('{}Equal timestamps for remote channel {} -- merging modes.{}'.format(Y, localChan.name, W), server=localServer)
                for member in memberlist:
                    rawUid = re.sub('[:*!~&@%+]', '', member)
                    if '*' in member:
                        giveModes.append('q')
                        giveParams.append(rawUid)
                    if '~' in member:
                        giveModes.append('a')
                        giveParams.append(rawUid)
                    if '@' in member:
                        giveModes.append('o')
                        giveParams.append(rawUid)
                    if '%' in member:
                        giveModes.append('h')
                        giveParams.append(rawUid)
                    if '+' in member:
                        giveModes.append('v')
                        giveParams.append(rawUid)

                for m in modes:
                    if m not in localChan.modes:
                        giveModes.append(m)
                    if m == 'k':
                        giveParams.append(key)
                    if m == 'l':
                        giveParams.append(limit)

                for b in [b for b in banlist if b not in localChan.bans]:
                    giveModes.append('b')
                    giveParams.append(b)

                for e in [e for e in excepts if e not in localChan.excepts]:
                    giveModes.append('e')
                    giveParams.append(e)

                for I in [I for I in invex if I not in localChan.invex]:
                    giveModes.append('I')
                    giveParams.append(I)

                data = []
                data.append(localChan.name)
                modes = '{}'.format('+'+''.join(giveModes) if giveModes else '')
                data.append(modes)
                for p in removeParams:
                    data.append(p)
                #if giveParams:
                #    data.append(':')
                for p in giveParams:
                    data.append(p)

        if modes and data:
            processModes(self, localServer, localChan, data, sync=True, sourceServer=self, sourceUser=self)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
