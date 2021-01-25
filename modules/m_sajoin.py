"""
/sajoin command
"""

import re

import ircd


class Sajoin(ircd.Command):
    """Forcefully join a user into a channel.
    Syntax: SAJOIN <user> <channel>
    """

    def __init__(self):
        self.command = 'sajoin'
        self.params = 2
        self.req_flags = ('localsacmds|globalsacmds')

    def execute(self, client, recv):
        target = next((c for c in self.ircd.users if c.nickname.lower() == recv[1].lower()))
        if not target:
            return client.sendraw(self.ERR.NOSUCHNICK, '{} :No such nick'.format(recv[1]))

        if target.server != self.ircd and not client.ocheck('o', 'globalsacmds'):
            return client.sendraw(self.ERR.NOPRIVILEGES, ':Permission denied - You do not have the correct IRC Operator privileges')

        if 'S' in target.modes or target.server in self.ircd.conf['settings']['ulines']:
            return self.ircd.notice(client, '*** You cannot use /SAJOIN on services.'.format(client.nickname))

        regex = re.compile('\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?', re.UNICODE)
        chan = regex.sub('', recv[2]).strip()

        channel = list(filter(lambda c: c.name.lower() == chan.lower(), self.ircd.channels))
        if not channel:
            return client.sendraw(self.ERR.NOSUCHCHANNEL, '{} :No such channel'.format(chan))

        chan = channel[0].name

        channel = list(filter(lambda c: c.name.lower() == chan.lower(), target.channels))
        if channel:
            return client.sendraw(self.ERR.USERONCHANNEL, '{} {} :is already on that channel'.format(target.nickname, channel[0].name))

        p = {'override': True}
        target.handle('join', chan, params=p)
        chan_class = [c for c in self.ircd.channels if c.name == chan][0]
        if target.server != self.ircd:
            ### Sync join to its server.
            prefix = ''
            for mode in [mode for mode in self.ircd.chprefix if mode in chan_class.usermodes[target]]:
                prefix += self.ircd.chprefix[mode]
            data = ':{} SJOIN {} {}{} :{}{}'.format(client.server.sid, chan_class.creation, chan_class.name, ' +{}'.format(chan_class.modes) if chan_class.modes and chan_class.users == [target] else '', prefix, target.uid)
            target.server._send(data)

        client.flood_penalty += 100000
        snomsg = '*** {} ({}@{}) used SAJOIN to make {} join {}'.format(client.nickname, client.ident, client.hostname, target.nickname, chan)
        self.ircd.snotice('S', snomsg)

        msg = '*** Your were forced to join {}.'.format(chan)
        self.ircd.notice(target, msg)
