#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/ison and /userhost command
"""

import ircd

@ircd.Modules.params(1)
@ircd.Modules.commands('ison')
def ison(self, localServer, recv):
    nicks = []
    for nick in recv[1:]:
        users = filter(lambda u: u.nickname.lower() == nick.lower() and u.registered, localServer.users)
        for user in [user for user in users if user.nickname not in nicks]:
            nicks.append(user.nickname)
    self.sendraw(303, ':{}'.format(' '.join(nicks)))

@ircd.Modules.params(1)
@ircd.Modules.commands('userhost')
def userhost(self, localServer, recv):
    hosts = []
    for nick in recv[1:]:
        users = filter(lambda u: u.nickname.lower() == nick.lower() and u.registered, localServer.users)
        for user in users:
            h = '{}*=+{}@{}'.format(user.nickname,user.ident,user.cloakhost if 'o' not in self.modes else user.hostname)
            if h not in hosts:
                hosts.append(h)
    self.sendraw(302, ':{}'.format(' '.join(hosts)))
