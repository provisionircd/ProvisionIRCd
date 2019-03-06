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

    users = []
    for user in channel.users:
        if 'i' in user.modes and (self not in channel.users and not self.ocheck('o', 'override') and not override):
            continue
        if '^' in user.modes:
            if not self.ocheck('o', 'stealth'):
                continue
            else:
                users.append('!'+user.nickname)
            continue

        ### Check module hooks for visible_in_channel()
        visible = 1
        if user != self:
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'visible_in_channel']:
                try:
                    visible = callable[2](self, localServer, user, channel)
                except Exception as ex:
                    _print('Exception in module: {}: {}'.format(callable[2], ex), server=localServer)
        if not visible:
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
