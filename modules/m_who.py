#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/who command
"""

import ircd
import os
import sys

from handle.functions import match, _print

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
            show, flagmatch = False, False
            ### Let's see if we have a match
            for m in mask.split(','):
                if match(m, user.nickname) or match(m, user.ident) or match(m, user.cloakhost) or match(m, user.server.hostname):
                    show = True

                chan_match = list(filter(lambda c: c.name.lower() == m.lower() and user in c.users, localServer.channels))
                if chan_match:
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
            if not user.channels:
                chan = '*'
            else:
                channel = None
                ### Assign a channel.
                for c in user.channels:
                    if ('s' in c.modes or 'p' in c.modes) and (self not in c.users and not self.ocheck('o', 'override')):
                        continue
                    else:
                        channel = c
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
            if not user.server:
                #print('User {} has no server? {}'.format(user.nickname, user.server))
                continue
            hopcount = 0 if user.server == localServer else user.server.hopcount
            self.sendraw(352, '{} {} {} {} {} {}{} :{} {}'.format(chan, user.ident, user.cloakhost, localServer.hostname, user.nickname, away, modes, hopcount, user.realname))
        self.sendraw(315, '* :End of /WHO list.')
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
