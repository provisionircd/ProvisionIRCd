import time
import os
import sys
from handle.functions import match, _print

def cmd_NICK(self, localServer, recv, sanick=False):
    try:
        ############################################################################################
        ### This should be at the start of every command, that requires syncing between servers. ###
        ############################################################################################
        if type(self).__name__ == 'Server':
            override = True
            _self = self
            self = list(filter(lambda u: u.uid == recv[0][1:], localServer.users))
            if not self:
                _self.quit('This port is for servers only', error=True)
                return
            ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
            self = self[0]
            recv = recv[1:]
        else:
            override = False

        if len(recv) < 2:
            self.sendraw(431, ':No nickname given')
            return

        nick = str(recv[1]).strip()
        if not override:
            nick = str(recv[1][:int('{}'.format(localServer.nicklen))]).strip()

        if nick.strip() == '':
            self.sendraw(431, ':No nickname given')
            return

        if self in localServer.nickflood and len(localServer.nickflood[self]) >= int(localServer.conf['settings']['nickflood'].split(':')[0]) and not self.ocheck('o', 'override') and not override and not sanick:
            self.sendraw(438, '{} :Nick change too fast. Please wait a while before attempting again.'.format(nick))
            return

        if nick[0].isdigit():
            self.sendraw(432, '{} :Erroneous nickname (Invalid: {})'.format(nick, nick[0]))
            return

        valid = 'abcdefghijklmnopqrstuvwxyz0123456789`^-_[]{}|\\'
        for c in nick:
            if c.lower() not in valid and not override:
                self.sendraw(432, '{} :Erroneous nickname (Invalid: {})'.format(nick, c))
                return
        inUse =  list(filter(lambda u: u.nickname.lower() == nick.lower(), localServer.users))
        if inUse and nick == self.nickname:
            ### Exact nick.
            return

        if inUse and nick.lower() != self.nickname.lower():
            self.sendraw(433, '{} :Nickname is already in use'.format(nick))
            return

        if 'Q' in localServer.tkl and not override:
            for entry in localServer.tkl['Q']:
                if match(entry.lower(), nick.lower()):
                    self.sendraw(432, '{} :Erroneous nickname ({})'.format(nick, localServer.tkl['Q'][entry]['reason']))
                    msg = '*** Q:Line Rejection -- Forbidden nick {} from client {} {}'.format(nick, self.ip, '[Current nick: {}]'.format(self.nickname) if self.nickname != '*' else '')
                    localServer.snotice('Q', msg)
                    return

        users = [self]
        for channel in self.channels:
            if 'N' in channel.modes and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override and not sanick:
                self.sendraw(447, ':{} Nick changes are not allowed on this channel'.format(channel.name))
                return
            for user in channel.users:
                if user not in users and user != self:
                    users.append(user)

        if self.registered:
            if self not in localServer.nickflood:
                localServer.nickflood[self] = {}
            localServer.nickflood[self][time.time()] = True
            if self.server == localServer:
                msg = '*** {} ({}@{}) has changed their nickname to {}'.format(self.nickname, self.ident, self.hostname, nick)
                self.server.snotice('N', msg)

            localServer.syncToServers(localServer, self.server, ':{} NICK {} {}'.format(self.uid, nick, int(time.time())))

            self.broadcast(users, 'NICK :{}'.format(nick))

            if self.nickname not in localServer.whowas:
                ### This list should contain additional dictionaries.
                localServer.whowas[self.nickname] = []
                whowasInfo = {}
                whowasInfo[self.nickname] = {}
                whowasInfo[self.nickname]['ident'] = self.ident
                whowasInfo[self.nickname]['cloakhost'] = self.cloakhost
                whowasInfo[self.nickname]['realname'] = self.realname
                whowasInfo[self.nickname]['hostname'] = self.hostname
                whowasInfo[self.nickname]['ip'] = self.ip
                whowasInfo[self.nickname]['server'] = self.server.hostname
                whowasInfo[self.nickname]['signoff'] = int(time.time())
                localServer.whowas[self.nickname].append(whowasInfo[self.nickname])

            ### <- :irc3.chattersweb.nl 601 bla bla provision 2FA9038F.7277B22A.71B7A79C.IP 1534463050 :logged offline
            ### Notify watchlist.
            #watch_lower = [x.lower() for x in user.watchlist]
            watch_notify_offline = [user for user in localServer.users if self.nickname.lower() in [x.lower() for x in user.watchlist]]
            watch_notify_online = [user for user in localServer.users if nick.lower() in [x.lower() for x in user.watchlist]]
            #print(watch_notify)
            ### 604 Y4kuzi Sirius uid143850 CW-6C9471D9.stonehaven.irccloud.com 1531187812 :is online
            for user in watch_notify_offline:
                user.sendraw(601, '{} {} {} {} :logged offline'.format(self.nickname, self.ident, self.cloakhost, self.signon))
            for user in watch_notify_online:
                user.sendraw(600, '{} {} {} {} :logged online'.format(nick, self.ident, self.cloakhost, self.signon))

        old = self.nickname
        self.nickname = nick

        if old == '*' and self.ident != '' and self.validping:
            self.welcome()

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION after accept: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
