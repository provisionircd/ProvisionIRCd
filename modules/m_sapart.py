"""
/sapart command
"""

import ircd
import re

@ircd.Modules.command
class Sapart(ircd.Command):
    """Forcefully part a user from a channel.
    Syntax: SAPART <user> <channel>
    """
    def __init__(self):
        self.command = 'sapart'
        self.params = 2
        self.req_flags = ('localsacmds|globalsacmds')

    def execute(self, client, recv):
        target = list(filter(lambda c: c.nickname.lower() == recv[1].lower(), self.ircd.users))
        if not target:
            return client.sendraw(self.ERR.NOSUCHNICK, '{} :No such nick'.format(recv[1]))

        if target[0].server != self.ircd and not client.ocheck('o', 'globalsacmds'):
            return client.sendraw(self.ERR.NOPRIVILEGES, ':Permission denied - You do not have the correct IRC Operator privileges')

        if 'S' in target[0].modes or target[0].server in self.ircd.conf['settings']['ulines']:
            return self.ircd.handle('NOTICE', '{} :*** You cannot use /SAPART on services.'.format(client.nickname))

        regex = re.compile('\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?', re.UNICODE)
        chan = regex.sub('', recv[2]).strip()

        channel = list(filter(lambda c: c.name.lower() == chan.lower(), self.ircd.channels))
        if not channel:
            return client.sendraw(self.ERR.NOSUCHCHANNEL, '{} :No such channel'.format(chan))

        channel = list(filter(lambda c: c.name.lower() == chan.lower(), target[0].channels))
        if not channel:
            return client.sendraw(self.ERR.USERNOTINCHANNEL, '{} {} :is not on that channel'.format(target[0].nickname, chan))

        client.flood_penalty += 100000
        channel = channel[0]
        target[0].handle('part', chan)

        snomsg = '*** {} ({}@{}) used SAPART to make {} part {}'.format(client.nickname, client.ident, client.hostname, target[0].nickname, channel.name)
        self.ircd.snotice('S', snomsg)
        msg = '*** Your were forced to part {}.'.format(channel.name)
        self.ircd.notice(target[0], msg)
