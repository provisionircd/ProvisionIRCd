#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/sajoin command
"""

import ircd
import re

@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('localsacmds|globalsacmds')
@ircd.Modules.commands('sajoin')
def sajoin(self, localServer, recv):
    target = list(filter(lambda c: c.nickname.lower() == recv[1].lower(), localServer.users))
    if not target:
        return self.sendraw(401, '{} :No such nick'.format(recv[1]))

    if target[0].server != localServer and not self.ocheck('o', 'globalsacmds'):
        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')

    if 'S' in target[0].modes or target[0].server in localServer.conf['settings']['ulines']:
        return localServer.notice(self, '*** You cannot use /SAJOIN on services.'.format(self.nickname))

    regex = re.compile('\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?', re.UNICODE)
    chan = regex.sub('', recv[2]).strip()

    channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))
    if not channel:
        return self.sendraw(401, '{} :No such channel'.format(chan))

    chan = channel[0].name

    channel = list(filter(lambda c: c.name.lower() == chan.lower(), target[0].channels))
    if channel:
        return self.sendraw(443, '{} {} :is already on that channel'.format(target[0].nickname, channel[0].name))

    p = {'override': True}
    target[0].handle('join', chan, params=p)

    snomsg = '*** {} ({}@{}) used SAJOIN to make {} join {}'.format(self.nickname, self.ident, self.hostname, target[0].nickname, chan)
    localServer.snotice('S', snomsg)

    msg = '*** Your were forced to join {}.'.format(chan)
    localServer.notice(target[0], msg)
