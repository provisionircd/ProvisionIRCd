#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/who command
"""

import ircd
import os
import sys

from handle.functions import match, logging

@ircd.Modules.support('WHOX')
@ircd.Modules.commands('who')
def who(self, localServer, recv):
    try:
        who, modes = [], ''
        mask, flags = None, None
        if len(recv) == 1 or recv[1] == '*':
            mask = '*' ### Match all.
        else:
            mask = recv[1]
            ### This parameter contains a comma-separated list of query filters,
            ### such as nicknames, channel names or wild-card masks which are matched against all clients currently on-line.
        if len(recv) > 2:
            ### Found flags.
            flags = recv[2]

        for user in localServer.users:
            chan = '*'
            show, flagmatch = False, False
            ### Let's see if we have a match
            for m in mask.split(','):
                if match(m, user.nickname) or match(m, user.ident) or match(m, user.cloakhost) or match(m, user.server.hostname):
                    show = True
                chan_match = list(filter(lambda c: c.name.lower() == m.lower() and user in c.users, localServer.channels))
                if chan_match:
                    chan = chan_match[0].name
                    visible = 1
                    for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'visible_in_channel']:
                        try:
                            visible = callable[2](self, localServer, user, chan_match[0])
                        except Exception as ex:
                            logging.exception(ex)
                        if not visible and user != self:
                            break
                    if not visible and user != self:
                        continue
                    show = True


                ### Now we filter out by flag. Flags have higher piority.
                if flags:
                    if not flagmatch:
                        show = False
                    if 'o' in flags and 'o' in user.modes:
                        show = True
                        flagmatch = True
                    if 'a' in flags and user.svid and user.svid != '*':
                        if m == '*' or m[0] in localServer.chantypes:
                            show = True
                            flagmatch = True
                        if (m != '*' or m[0] in localServer.chantypes) and m.lower() == user.svid.lower():
                            show = True
                            flagmatch = True

                    if 'r' in flags and match(m, user.realname):
                        show = True
                        flagmatch = True

                    ### Checks in case we need to reverse the initial checks.
                    #if 'n' in flags and not match(m, user.nickname):
                    #    show = False
                    #if 'u' in flags and not match(m, user.ident):
                    #    show = False
                    #if 'h' in flags and not match(m, user.cloakhost):
                    #    show = False
                    if 's' in flags and match(m, user.server.hostname):
                        show = True
                        flagmatch = True

            #print('Showing user {}: {}'.format(user, show))
            if not show:
                continue

            chanMatch = False
            if 'i' in user.modes:
                for c in user.channels:
                    if c in self.channels or self.ocheck('o', 'override'):
                        #_print(c)
                        chanMatch = True
                        break
                if not chanMatch and not self.ocheck('o', 'override'):
                    continue
            modes = ''
            if user in who:
                continue
            who.append(user)
            if user.channels and chan == '*':
                channel = None
                ### Assign a channel.
                for c in user.channels:
                    if ('s' in c.modes or 'p' in c.modes) and (self not in c.users and not self.ocheck('o', 'override')):
                        continue
                    else:
                        channel = c

                    visible = 1
                    for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'visible_in_channel']:
                        try:
                            visible = callable[2](self, localServer, user, channel)
                        except Exception as ex:
                            logging.exception(ex)
                        if not visible:
                            break
                    if not visible and user != self:
                        channel = None
                        continue

                if not channel:
                    continue
                #channel = user.channels[0]
                chan = channel.name
                modes = ''.join([{'q': '~', 'a': '&', 'o': '@', 'h': '%', 'v': ''}[x] for x in channel.usermodes[user]])
            if 'x' in user.modes:
                modes += 'x'
            if user.away:
                away = 'G'
            else:
                away = 'H'
            if 'r' in user.modes:
                modes += 'r'
            if 'o' in user.modes and 'H' not in user.modes:
                modes += '*'
            if 'H' in user.modes:
                modes += '?'
            if 'z' in user.modes:
                modes += 'z'
            if not user.server:
                #print('User {} has no server? {}'.format(user.nickname, user.server))
                continue
            hopcount = 0 if user.server == localServer else user.server.hopcount
            self.sendraw(352, '{} {} {} {} {} {}{} :{} {}'.format(chan, user.ident, user.cloakhost, localServer.hostname, user.nickname, away, modes, hopcount, user.realname))
        self.sendraw(315, '* :End of /WHO list.')
    except Exception as ex:
        logging.exception(ex)
