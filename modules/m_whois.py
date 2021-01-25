"""
/whois and /whowas command
"""

import ircd

import datetime
import time
from handle.functions import logging


class Whois(ircd.Command):
    """Displays information about the given user, such as hostmask, channels, idle time, etc...
    Output may vary depending on user- and channel modes.

    Example: WHOIS Bob
    """

    def __init__(self):
        self.command = 'whois'

    def execute(self, client, recv):
        # localServer = self.ircd
        # self = user
        if len(recv) < 2:
            self.sendraw(431, ':No nickname given')
            return
        user = list(filter(lambda u: u.nickname.lower() == recv[1].lower(), self.ircd.users))

        if not user or not user[0].registered:
            client.sendraw(401, '{} :No such nick'.format(recv[1]))
            client.sendraw(318, '{} :End of /WHOIS list.'.format(recv[1]))
            return

        user = user[0]

        if 'W' in user.modes and user != client:
            msg = '*** Notice -- {s.nickname} ({s.ident}@{s.hostname}) did a /WHOIS on you.'.format(s=client)
            # us = list(filter(lambda u: u.nickname == user.nickname and user.server == self.ircd, self.ircd.users)) # Wat?
            # u = [u for u in self.ircd.users if u.nickname == user.nickname]
            if user.server == self.ircd:  # Local
                client.server.broadcast([user], 'NOTICE {} :{}'.format(user.nickname, msg))
            else:
                data = ':{} NOTICE {} :{}'.format(self.ircd.hostname, user.nickname, msg)
                sock = user.server if user.server.socket else user.server.introducedBy
                sock._send(data)

        client.sendraw(311, '{} {} {} * :{}'.format(user.nickname, user.ident, user.cloakhost, user.realname))

        if 'o' in client.modes or user == client:
            client.sendraw(379, '{} :is using modes: +{} {}'.format(user.nickname, user.modes, '+' + user.snomasks if user.snomasks else ''))

        if ('o' in client.modes or user == client) and user.server.hostname not in self.ircd.conf['settings']['ulines'] and 'S' not in user.modes:
            client.sendraw(378, '{} :is connecting from *@{} {}'.format(user.nickname, user.hostname, user.ip))

        if 'r' in user.modes:
            client.sendraw(307, '{} :is identified for this nick'.format(user.nickname))

        if 'c' not in user.modes or 'o' in client.modes or user == client:
            if user.channels and user.server.hostname not in self.ircd.conf['settings']['ulines'] and 'S' not in user.modes:
                channels = []
                for channel in user.channels:
                    visible = 1
                    for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'visible_in_channel']:
                        try:
                            visible = callable[2](client, self.ircd, user, channel)
                        except Exception as ex:
                            logging.exception(ex)
                        if not visible:
                            break
                    if not visible:
                        continue

                    prefix = ''
                    if visible == 2:
                        prefix += '?'
                    if '^' in user.modes and not client.ocheck('o', 'stealth'):
                        continue
                    if '^' in user.modes:
                        prefix = '^'
                    if 's' in channel.modes or 'p' in channel.modes:
                        if user != client and client not in channel.users and 'o' not in client.modes:
                            continue
                        if '!' not in prefix and '?' not in prefix:
                            prefix += '?'
                    if 'c' in user.modes and ('o' in client.modes or user == client) and '?' not in prefix:
                        prefix += '!'
                    if 'q' in channel.usermodes[user]:
                        prefix += '~'
                    if 'a' in channel.usermodes[user]:
                        prefix += '&'
                    if 'o' in channel.usermodes[user]:
                        prefix += '@'
                    if 'h' in channel.usermodes[user]:
                        prefix += '%'
                    if 'v' in channel.usermodes[user]:
                        prefix += '+'
                    channels.append('{}{}'.format(prefix, channel.name))
                if channels:
                    client.sendraw(319, '{} :{}'.format(user.nickname, ' '.join(channels)))

        client.sendraw(312, '{} {} :{}'.format(user.nickname, user.server.hostname, user.server.name))

        if user.away:
            client.sendraw(301, '{} :{}'.format(user.nickname, user.away))

        if 'H' not in user.modes or 'o' in client.modes:
            if 'o' in user.modes and 'S' not in user.modes:
                show_acc = True if user.operaccount and (user == client or (client.operaccount and client.operaccount == user.operaccount)) else False
                client.sendraw(313, '{} :is an IRC Operator{}'.format(user.nickname, ' [{}]'.format(user.operaccount) if 'o' in client.modes and show_acc else ''))

        if 'B' in user.modes:
            client.sendraw(335, '{} :is a bot on {}'.format(user.nickname, user.server.name))

        if 'z' in user.modes and 'S' not in user.modes and user.server.hostname not in self.ircd.conf['settings']['ulines']:
            client.sendraw(671, '{} :is using a secure connection'.format(user.nickname))

            if user.fingerprint:
                client.sendraw(276, '{} :has client certificate fingerprint {}'.format(user.nickname, user.fingerprint))

        # Read below.
        if 'H' not in user.modes or 'o' in client.modes:  ### TODO: only exclude oper-whois on +H. Other swhois should be visible.
            for line in user.swhois:
                client.sendraw(320, '{} :{}'.format(user.nickname, line))

        if hasattr(user, 'svid') and user.svid != '*':
            client.sendraw(330, '{} {} :is using acount'.format(user.nickname, user.svid))

        if self.ircd.hostname == user.server.hostname or 'o' in client.modes and 'S' not in user.modes and user.server.hostname not in self.ircd.conf['settings']['ulines']:
            client.sendraw(317, '{} {} {} :seconds idle, signon time'.format(user.nickname, int(time.time()) - user.idle, user.signon))

        if 'S' in user.modes:
            client.sendraw(313, '{} :is a Network Service'.format(user.nickname))

        client.sendraw(318, '{} :End of /WHOIS list.'.format(user.nickname))


class Whowas(ircd.Command):
    """Request saved user information for offline users.
    -
    Example: WHOWAS ZoeyDeutch
    """

    def __init__(self):
        self.command = 'whowas'

    def execute(self, client, recv):
        if len(recv) < 2:
            return client.sendraw(431, ':No nickname given')
        isWhowas = False
        if not hasattr(self.ircd, 'whowas'):
            self.ircd.whowas = {}
        for nick in self.ircd.whowas:
            if nick.lower() == recv[1].lower():
                isWhowas = True
                for info in self.ircd.whowas[nick]:
                    ident = info['ident']
                    cloakhost = info['cloakhost']
                    realname = info['realname']
                    hostname = info['hostname']
                    ip = info['ip']
                    signoff = int(info['signoff'])
                    d = datetime.datetime.fromtimestamp(signoff).strftime('%a %b %d')
                    t = datetime.datetime.fromtimestamp(signoff).strftime('%H:%M:%S %Z').strip()
                    y = datetime.datetime.fromtimestamp(signoff).strftime('%Y')
                    server = info['server']
                    client.sendraw(314, '{} {} {} * :{}'.format(nick, ident, cloakhost, realname))
                    if 'o' in client.modes:
                        client.sendraw(378, '{} :connected from *@{} {}'.format(nick, hostname, ip))
                    client.sendraw(312, '{} {} :{} {} {}'.format(nick, server, d, t, y))

        if not isWhowas:
            client.sendraw(406, '{} :There was no such nickname'.format(recv[1]))
            client.sendraw(369, '{} :End of /WHOWAS list.'.format(recv[1]))
            return

        self.sendraw(369, '{} :End of /WHOWAS list.'.format(recv[1]))


@ircd.Modules.hooks.local_quit()
@ircd.Modules.hooks.remote_quit()
@ircd.Modules.hooks.local_nickchange()
@ircd.Modules.hooks.remote_nickchange()
def savewhowas(self, ircd):
    try:
        if type(self).__name__ == 'Server' or not self.registered:
            return
        if not hasattr(ircd, 'whowas'):
            ircd.whowas = {}
        if self.nickname not in ircd.whowas:
            ircd.whowas[self.nickname] = []
        whowasInfo = {self.nickname: {}}
        whowasInfo[self.nickname]['ident'] = self.ident
        whowasInfo[self.nickname]['cloakhost'] = self.cloakhost
        whowasInfo[self.nickname]['realname'] = self.realname
        whowasInfo[self.nickname]['hostname'] = self.hostname
        whowasInfo[self.nickname]['ip'] = self.ip
        whowasInfo[self.nickname]['server'] = self.server.hostname
        whowasInfo[self.nickname]['signoff'] = int(time.time())

        ircd.whowas[self.nickname].append(whowasInfo[self.nickname])
        if len(ircd.whowas[self.nickname]) > 12:
            del ircd.whowas[self.nickname][0]

        for nick in dict(ircd.whowas):
            info = list(ircd.whowas[nick])
            for data in info:
                signoff = data['signoff']
                if int(time.time()) - signoff > 3600 * 24 * 30:  ### 1 month expire?
                    ircd.whowas[nick].remove(data)

    except Exception as ex:
        logging.exception(ex)


class Umode_c(ircd.UserMode):
    def __init__(self):
        self.mode = 'c'
        self.desc = 'Hide channels in /WHOIS'


class Umode_W(ircd.UserMode):
    def __init__(self):
        self.mode = 'W'
        self.desc = 'See when people are doing a /WHOIS on you'
        self.req_flag = 1
