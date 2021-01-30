"""
/nick command
"""

import time

import ircd
from handle.functions import match

NICKLEN = 33


class Nick(ircd.Command):
    """
    Changes your nickname. Users you share a channel with will be notified of this change.
    Syntax: /NICK <newnick>
    """

    def __init__(self):
        self.command = 'nick'
        self.params = 1
        self.support = [('NICKLEN', NICKLEN), ]

    def execute(self, client, recv, override=False, sanick=False):
        if type(client).__name__ == 'Server':
            sourceServer = client
            override = True
            _client = client
            # If the first param is not a UID, it means a new client is trying to connect.
            # Closing connection.
            client = [u for u in self.ircd.users if u.uid == recv[0][1:]]
            if not client:
                _client.quit('This port is for servers only')
                return

            client = client[0]
            recv = recv[1:]
            hook = 'remote_nickchange'
        else:

            sourceServer = self.ircd
            hook = 'local_nickchange'

        if len(recv) < 2:
            return client.sendraw(431, ':No nickname given')

        nick = str(recv[1]).strip()
        if not override:
            nick = str(recv[1][:int(self.ircd.nicklen)]).strip()

        if nick.strip() == '':
            return client.sendraw(431, ':No nickname given')

        if nick[0].isdigit():
            return client.sendraw(432, '{} :Erroneous nickname (Invalid: {})'.format(nick, nick[0]))

        valid = 'abcdefghijklmnopqrstuvwxyz0123456789`^-_[]{}|\\'
        for c in nick:
            if c.lower() not in valid and not override:
                return client.sendraw(432, '{} :Erroneous nickname (Invalid: {})'.format(nick, c))

        if sanick:
            override = True

        if client in self.ircd.nickflood and len(self.ircd.nickflood[client]) >= int(self.ircd.conf['settings']['nickflood'].split(':')[0]) and 'o' not in client.modes and not override:
            client.flood_penalty += 150000
            return client.sendraw(438, '{} :Nick change too fast. Please wait a while before attempting again.'.format(nick))

        inUse = list(filter(lambda u: u.nickname.lower() == nick.lower(), self.ircd.users))
        if inUse and nick == client.nickname:
            # Exact nick.
            return

        if inUse and nick.lower() != client.nickname.lower():
            return client.sendraw(433, '{} :Nickname is already in use'.format(nick))

        if 'Q' in self.ircd.tkl and not override:
            for entry in [entry for entry in self.ircd.tkl['Q'] if entry != '*']:
                if match(entry.split('@')[1].lower(), nick.lower()):
                    client.sendraw(432, '{} :Erroneous nickname ({})'.format(nick, self.ircd.tkl['Q'][entry]['reason']))
                    msg = '*** Q:Line Rejection -- Forbidden nick {} from client {} {}'.format(nick, client.ip, '[Current nick: {}]'.format(client.nickname) if client.nickname != '*' else '')
                    return self.ircd.snotice('Q', msg)

        users = [client]
        for channel in client.channels:
            if 'N' in channel.modes and client.chlevel(channel) < 5 and not client.ocheck('o', 'override') and not override:
                return client.sendraw(447, ':{} Nick changes are not allowed on this channel'.format(channel.name))

            for u in channel.users:
                if u not in users and u != client:
                    users.append(u)

            if sourceServer == self.ircd:  ### pre_local_nickchanage
                success = 1
                for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'pre_' + hook]:
                    try:
                        success = callable[2](client, self.ircd)
                        if not success and success is not None:  ### None will default to True.
                            break
                    except Exception as ex:
                        logging.exception(ex)
                if not success:
                    return

        if client.registered:
            if client not in self.ircd.nickflood:
                self.ircd.nickflood[client] = {}
            self.ircd.nickflood[client][time.time()] = True
            if client.server == self.ircd and not sanick:
                msg = '*** {} ({}@{}) has changed their nickname to {}'.format(client.nickname, client.ident, client.hostname, nick)
                client.server.snotice('N', msg)

            if sanick and type(sanick).__name__ == 'User':
                snomsg = '*** {} ({}@{}) used SANICK to change nickname {} to {}'.format(sanick.nickname, sanick.ident, sanick.hostname, client.nickname, nick)
                self.ircd.snotice('S', snomsg)

                msg = '*** Your nick has been forcefully changed by  {}.'.format(sanick.nickname)
                self.ircd.handle('NOTICE', '{} :{}'.format(client.nickname, msg))

            ### Check module hooks for visible_in_channel()
            all_broadcast = [client]
            for channel in client.channels:
                for u in channel.users:
                    if u not in all_broadcast and u != client:
                        all_broadcast.append(u)
            for u in [u for u in all_broadcast if u != client]:
                visible = 0
                for channel in client.channels:
                    for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'visible_in_channel']:
                        try:
                            visible = callable[2](u, self.ircd, client, channel)
                            # logging.debug('Is {} visible for {} on {}? :: {}'.format(client.nickname, u.nickname, channel.name, visible))
                        except Exception as ex:
                            logging.exception(ex)
                    if visible:  ### Break out of the channels loop. No further checks are required.
                        break
                if not visible:
                    logging.debug('User {} is not allowed to see {} on any channel, not sending nickchange.'.format(u.nickname, client.nickname))
                    all_broadcast.remove(u)

            client.broadcast(all_broadcast, 'NICK :{}'.format(nick))
            self.ircd.new_sync(self.ircd, sourceServer, ':{} NICK {} {}'.format(client.uid, nick, int(time.time())))

            watch_notify_offline = [u for u in self.ircd.users if client.nickname.lower() in [x.lower() for x in u.watchlist]]
            watch_notify_online = [u for u in self.ircd.users if nick.lower() in [x.lower() for x in u.watchlist]]
            for watch_user in watch_notify_offline:
                watch_user.sendraw(601, '{} {} {} {} :logged offline'.format(client.nickname, client.ident, client.cloakhost, client.signon))
            for watch_user in watch_notify_online:
                watch_user.sendraw(600, '{} {} {} {} :logged online'.format(nick, client.ident, client.cloakhost, client.signon))

            for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == hook]:
                try:
                    callable[2](client, self.ircd)
                except Exception as ex:
                    logging.exception(ex)

        old = client.nickname
        client.nickname = nick

        if old == '*' and client.ident != '' and client.validping and (client.cap_end or not client.sends_cap):
            client.welcome()


@ircd.Modules.hooks.loop()
def expired_nickflood(localServer):
    if hasattr(localServer, 'nickflood'):
        for user in [user for user in localServer.users if user in localServer.nickflood]:
            for nickchg in (nickchg for nickchg in dict(localServer.nickflood[user]) if int(time.time()) - int(nickchg) > int(localServer.conf['settings']['nickflood'].split(':')[1])):
                del localServer.nickflood[user][nickchg]
                continue


def init(ircd, reload=False):
    ircd.nickflood = {}
    ircd.nicklen = NICKLEN
