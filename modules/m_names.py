#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/names command
"""

import ircd

from handle.functions import _print

@ircd.Modules.params(1)
@ircd.Modules.commands('names')
def names(self, localServer, recv, override=False):
    channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), localServer.channels))
    if not channel:
        return self.sendraw(401, '{} :No such channel'.format(recv[1]))

    channel = channel[0]
    success, exclude = True, []
    for callable in [callable for callable in localServer.events if callable[0].lower() == 'pre_names']:
        try:
            success, exclude = callable[1](self, localServer, channel)
        except Exception as ex:
            _print(ex, server=localServer)

    users = []
    for user in [user for user in channel.users if user not in exclude]:
        if 'i' in user.modes and (self not in channel.users and not self.ocheck('o', 'override') and not override):
            continue
        if '^' in user.modes:
            if not self.ocheck('o', 'stealth'):
                continue
            else:
                users.append('!'+user.nickname)
            continue

        prefix = ''
        for mode in [mode for mode in localServer.chprefix if mode in channel.usermodes[user]]:
            prefix += localServer.chprefix[mode]

        string = ''
        if 'userhost-in-names' in self.caplist:
            string = '!{}@{}'.format(user.ident, user.cloakhost)
        entry = '{}{}'.format(user.nickname, string)
        users.append(prefix+''+entry)

        if len(users) >= 24:
            self.sendraw(353, '= {} :{}'.format(channel.name, ' '.join(users)))
            users = []
            continue

    self.sendraw(353, '= {} :{}'.format(channel.name, ' '.join(users)))
    self.sendraw(366, '{} :End of /NAMES list.'.format(channel.name))
