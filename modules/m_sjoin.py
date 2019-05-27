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
from handle.functions import logging

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
            logging.error('{}ERROR: received a local channel from remote server: {}{}'.format(R, channel, W))
            self.squit('Sync error! Remote server tried to link local channels.')
            return

        if not self.eos:
            localServer.new_sync(localServer, self, raw)
        localServer.parammodes = localServer.chstatus
        for x in range(0, 4):
            for m in [m for m in localServer.channel_modes[x] if str(x) in '012' and m not in localServer.parammodes]:
                localServer.parammodes += m
        memberlist = []
        banlist = []
        excepts = []
        invex = []
        c = 0
        for pos in recv[1:]:
            c += 1
            if pos.startswith(':'):
                memberlist = ' '.join(recv[c:]).split('&')[0].split('"')[0].split("'")[0][1:].split()
                continue
            if pos.startswith('&'):
                banlist.append(pos[1:])
            if pos.startswith('"'):
                excepts.append(pos[1:])
            if pos.startswith("'"):
                invex.append(pos[1:])

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

        for member in memberlist:
            membernick = []
            for c in member:
                if c not in ':*~@%+':
                    membernick.append(c)
            membernick = ''.join(membernick)

            userClass = list(filter(lambda c: c.nickname.lower() == membernick.lower() or c.uid == membernick, localServer.users))
            if not userClass:
                logging.error('{}ERROR: could not fetch userclass for remote user {}. Looks like the user did not sync correctly. Maybe nick collision, or remote leftover from a netsplit.{}'.format(R, membernick, W))
                ##continue
                #source.quit('ERROR: could not fetch userclass for remote user {}. Looks like the user did not sync correctly. Maybe nick collision, or remote leftover from a netsplit.'.format(membernick))
                continue

            userClass = userClass[0]
            p = {'override': True, 'sourceServer': self}
            userClass.handle('join', channel, params=p)
            localChan = list(filter(lambda c: c.name.lower() == channel.lower(), localServer.channels))[0]
            if len(localChan.users) == 1:
                ### Channel did not exist on localServer. Hook channel_create? Sure, why not.
                pass
            if userClass.server != localServer:
                logging.info('{}External user {} joined {} on local server.{}'.format(G, userClass.nickname, channel, W))
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
            # Remote channel is dominant. Replacing modes with remote channel
            # Clear the local modes.
            #
            logging.info('Remote channel {} is dominant. Replacing modes with remote channel'.format(channel))
            localChan.creation = timestamp
            localChan.name = channel
            pc = 5
            for m in localChan.modes:
                if m not in modes and m in list(localServer.channel_modes[2])+list(localServer.channel_modes[3]):
                    removeModes.append(m)
                    continue
                ### Remote info is different, remove old one first.
                if m in localServer.channel_modes[1] and localServer.chan_params[localChan][m] != recv[pc]:
                    removeParams.append(localServer.chan_params[localChan][m])
                    removeModes.append(m)
                if m in localServer.parammodes:
                    pc += 1

            pc = 5
            for m in modes:
                if m not in localChan.modes and m in localServer.channel_modes[3]:
                    giveModes.append(m)
                    continue
                if m in localServer.parammodes:
                    giveModes.append(m)
                    giveParams.append(recv[pc])
                    logging.debug('SJOIN: Mode {} has param: {}'.format(m, recv[pc]))
                    pc += 1

            # Removing local channel user modes.
            for user in localChan.users:
                for m in localChan.usermodes[user]:
                    removeModes.append(m)
                    removeParams.append(user.nickname)

            for b in [b for b in localChan.bans if b not in banlist]:
                removeModes.append('b')
                removeParams.append(b)

            for e in [e for e in localChan.excepts if e not in excepts]:
                removeModes.append('e')
                removeParams.append(e)

            for I in [I for I in localChan.invex if I not in invex]:
                removeModes.append('I')
                removeParams.append(I)

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
            modes = '{}{}'.format('-'+''.join(removeModes) if removeModes else '', '+'+''.join(giveModes) if giveModes else '')
            data.append(modes)
            for p in removeParams:
                data.append(p)
            for p in giveParams:
                data.append(p)

        elif timestamp == localChan.creation and not source.eos:
            if modes:
                logging.info('{}Equal timestamps for remote channel {} -- merging modes.{}'.format(Y, localChan.name, W))
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
                pc = 5
                for m in modes:
                    if m not in localChan.modes:
                        giveModes.append(m)
                        if m in localServer.parammodes:
                            giveParams.append(recv[pc])
                            pc += 1
                        continue

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
                for p in giveParams:
                    data.append(p)

        if modes and data:
            processModes(self, localServer, localChan, data, sync=True, sourceServer=self, sourceUser=self)

    except Exception as ex:
        logging.exception(ex)
