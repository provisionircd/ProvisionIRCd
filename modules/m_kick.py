"""
/kick command
"""

import ircd

from handle.functions import logging

KICKLEN = 312

@ircd.Modules.command
class Kick(ircd.Command):
    """Syntax: KICK <channel> <user> [reason]

    As a channel operator, you kick users from your channel.
    """
    def __init__(self):
        self.command = 'kick'
        self.params = 2
        self.support = [('KICKLEN', KICKLEN,)]


    def execute(self, client, recv, override=False, sync=True):
        oper_override = False
        if type(client).__name__ == 'Server':
            hook = 'remote_kick' if client != self.ircd else 'local_kick'
            override = True
            sourceServer = client
            S = recv[0][1:]
            source = [s for s in self.ircd.servers+[self.ircd] if s.sid == S or s.hostname == S]+[u for u in self.ircd.users if u.uid == S or u.nickname == S]
            client = source[0]
            recv = recv[1:]
            if type(client).__name__ == 'User':
                sourceID = client.uid
            else:
                sourceID = client.sid
        else:
            hook = 'local_kick'
            sourceServer = client.server
            sourceID = client.uid

        chan = recv[1]

        channel = list(filter(lambda c: c.name.lower() == chan.lower(), self.ircd.channels))

        if not channel:
            return client.sendraw(self.ERR.NOSUCHCHANNEL, '{} :No such channel'.format(chan))

        channel = channel[0]

        if type(client).__name__ != 'Server':
            if client.chlevel(channel) < 2 and not client.ocheck('o', 'override') and not override:
                return client.sendraw(482, '{} :You\'re not a channel operator'.format(channel.name))

            elif client.chlevel(channel) < 2:
                oper_override = True
        # Set the userclass of the target.
        user = list(filter(lambda u: (u.nickname.lower() == recv[2].lower() or u.uid.lower() == recv[2].lower()) and '^' not in u.modes, self.ircd.users))

        if not user:
            client.sendraw(self.ERR.NOSUCHNICK, '{} :No such nick'.format(recv[2]))
            return

        user = user[0]

        if channel not in user.channels:
            return client.sendraw(441, '{} :User {} isn\'t on that channel'.format(channel.name, user.nickname))

        if (user.chlevel(channel) > client.chlevel(channel) or 'q' in user.modes) and not client.ocheck('o', 'override') and not override:
            return client.sendraw(972, '{} :You cannot kick {}{}'.format(channel.name, user.nickname,' (+q)' if 'q' in user.modes else ''))

        elif user.chlevel(channel) > client.chlevel(channel) or 'q' in user.modes:
            oper_override = True

        if 'Q' in channel.modes and client.chlevel(channel) < 5 and not client.ocheck('o', 'override') and not override:
            return client.sendraw(404, '{} :KICKs are not permitted in this channel'.format(channel.name))

        elif 'Q' in channel.modes and client.chlevel(channel) < 5 and not override:
            oper_override = True
        if len(recv) == 3:
            reason = client.nickname
        else:
            reason = ' '.join(recv[3:])
        if reason[0] == ':':
            reason = reason[1:]
        reason = reason[:KICKLEN]

        broadcast = list(channel.users)
        ### Check module hooks for visible_in_channel()
        for u in broadcast:
            visible = 1
            for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'visible_in_channel']:
                try:
                    visible = callable[2](u, self.ircd, user, channel)
                except Exception as ex:
                    logging.exception(ex)
                if not visible:
                    broadcast.remove(u)
                    logging.debug('/KICK: User {} is not allowed to see {} on channel {}'.format(u.nickname, user.nickname, channel.name))
                    break

        if type(client).__name__ == 'User':
            success = True
            for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'pre_local_kick']:
                try:
                    success = callable[2](client, self.ircd, user, channel, reason)
                    if not success and success is not None:
                        logging.debug('KICK denied by: {}'.format(callable))
                        break
                except Exception as ex:
                    logging.exception(ex)
            if not success and success is not None:
                return

        if oper_override:
            client.server.snotice('s', '*** OperOverride by {} ({}@{}) with KICK {} {} ({})'.format(client.nickname, client.ident, client.hostname, channel.name, user.nickname, reason))

        client.broadcast(broadcast, 'KICK {} {} :{}'.format(channel.name, user.nickname, reason))
        user.channels.remove(channel)
        channel.users.remove(user)
        channel.usermodes.pop(user)

        if len(channel.users) == 0 and 'P' not in channel.modes:
            self.ircd.channels.remove(channel)
            del self.ircd.chan_params[channel]
            for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'channel_destroy']:
                try:
                    callable[2](client, self.ircd, channel)
                except Exception as ex:
                    logging.exception(ex)

        for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == hook]:
            try:
                callable[2](client, self.ircd, user, channel, reason)
            except Exception as ex:
                logging.exception(ex)

        if sync:
            self.ircd.new_sync(self.ircd, sourceServer, ':{} KICK {} {} :{}'.format(sourceID, channel.name, user.nickname, reason))
