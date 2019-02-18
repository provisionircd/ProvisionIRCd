#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/sapart command
"""

import ircd
import re

@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('localsacmds|globalsacmds')
@ircd.Modules.commands('sapart')
def sapart(self, localServer, recv):
    target = list(filter(lambda c: c.nickname.lower() == recv[1].lower(), localServer.users))
    if not target:
        return self.sendraw(401, '{} :No such nick'.format(recv[1]))

    if target[0].server != localServer and not self.ocheck('o', 'globalsacmds'):
        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')

    if 'S' in target[0].modes or target[0].server in localServer.conf['settings']['ulines']:
        return localServer.handle('NOTICE', '{} :*** You cannot use /SAPART on services.'.format(self.nickname))

    regex = re.compile('\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?', re.UNICODE)
    chan = regex.sub('', recv[2]).strip()

    channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))
    if not channel:
        return self.sendraw(401, '{} :No such channel'.format(chan))

    channel = list(filter(lambda c: c.name.lower() == chan.lower(), target[0].channels))
    if not channel:
        return self.sendraw(441, '{} {} :is not on that channel'.format(target[0].nickname, chan))

    channel = channel[0]

    snomsg = '*** {} ({}@{}) used SAPART to make {} part {}'.format(self.nickname, self.ident, self.hostname, target[0].nickname, channel.name)
    localServer.snotice('S', snomsg)

    msg = '*** Your were forced to part {}.'.format(channel.name)

    #p = {'sapart': self}
    target[0].handle('part', chan)

    localServer.notice(target[0], msg)
