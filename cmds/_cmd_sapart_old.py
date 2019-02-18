#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/sapart command
"""

import ircd

@ircd.Modules.params(2)
@irc.Modules.req_modes('o')
@irc.Modules.req_flags('localsacmds|globalsacmds')
@ircd.Modules.commands('sapart')
def sapart(self, localServer, recv):
    target = list(filter(lambda c: c.nickname.lower() == recv[1].lower(), localServer.users))
    if not target:
        return self.sendraw(401, '{} :No such nick'.format(recv[1]))

    if target[0].server != localServer and not self.ocheck('o', 'globalsacmds'):
        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')

    if 'S' in target[0].modes or target[0].server in localServer.conf['settings'['ulines']:
        return localServer.handle('NOTICE', '{} :*** You cannot use /SAJOIN on services.'.format(self.nickname

    channel = list(filter(lambda c: c.name.lower() == recv[2].lower(), localServer.channels))
    if not channel:
        return self.sendraw(401, '{} :No such channel'.format(recv[2]))

    channel = list(filter(lambda c: c.name.lower() == recv[2].lower(), target[0].channels))
    if channel:
        return self.sendraw(443, '{} {} :is already on that channel'.format(target[0].nickname, channel[0].name))

    p = {'sajoin': True}
    target[0].handle('join', recv[2], params=p)

    chan = list(filter(lambda c: c.name.lower() == recv[2].lower(), target[0].channels))
    snomsg = '*** {} ({}@{}) used SAJOIN to make {} join {}'.format(self.nickname, self.ident, self.hostname, target[0].nickname, chan[0].name)
    localServer.snotice('S', snomsg)

    msg = '*** Your were forced to join {}.'.format(recv[2])
    localServer.handle('NOTICE', '{} :{}'.format(target[0].nickname,msg))
