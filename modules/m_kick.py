"""
/kick command
"""

import ircd

from handle.functions import logging

kicklen = 312

@ircd.Modules.params(2)
@ircd.Modules.support('KICKLEN='+str(kicklen))
@ircd.Modules.commands('kick')
def kick(self, localServer, recv, override=False, sync=True):
    """Syntax: KICK <channel> <user> [reason]
-
As a channel operator, you kick users from your channel."""

    try:
        oper_override = False
        if type(self).__name__ == 'Server':
            hook = 'remote_kick' if self != localServer else 'local_kick'
            override = True
            sourceServer = self
            S = recv[0][1:]
            source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
            self = source[0]
            recv = recv[1:]
            if type(self).__name__ == 'User':
                sourceID = self.uid
            else:
                sourceID = self.sid
        else:
            hook = 'local_kick'
            sourceServer = self.server
            sourceID = self.uid

        chan = recv[1]

        channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))

        if not channel:
            return self.sendraw(401, '{} :No such channel'.format(chan))

        channel = channel[0]

        if type(self).__name__ != 'Server':
            if self.chlevel(channel) < 2 and not self.ocheck('o', 'override') and not override:
                return self.sendraw(482, '{} :You\'re not a channel operator'.format(channel.name))

            elif self.chlevel(channel) < 2:
                oper_override = True
        # Set the userclass of the target.
        user = list(filter(lambda u: (u.nickname.lower() == recv[2].lower() or u.uid.lower() == recv[2].lower()) and '^' not in u.modes, localServer.users))

        if not user:
            self.sendraw(401, '{} :No such nick'.format(recv[2]))
            return

        user = user[0]

        if channel not in user.channels:
            return self.sendraw(441, '{} :User {} isn\'t on that channel'.format(channel.name, user.nickname))

        if (user.chlevel(channel) > self.chlevel(channel) or 'q' in user.modes) and not self.ocheck('o', 'override') and not override:
            return self.sendraw(972, '{} :You cannot kick {}{}'.format(channel.name, user.nickname,' (+q)' if 'q' in user.modes else ''))

        elif user.chlevel(channel) > self.chlevel(channel) or 'q' in user.modes:
            oper_override = True

        if 'Q' in channel.modes and self.chlevel(channel) < 5 and not self.ocheck('o', 'override') and not override:
            return self.sendraw(404, '{} :KICKs are not permitted in this channel'.format(channel.name))

        elif 'Q' in channel.modes and self.chlevel(channel) < 5 and not override:
            oper_override = True
        if len(recv) == 3:
            reason = self.nickname
        else:
            reason = ' '.join(recv[3:])
        if reason[0] == ':':
            reason = reason[1:]
        reason = reason[:kicklen]

        broadcast = list(channel.users)
        ### Check module hooks for visible_in_channel()
        for u in broadcast:
            visible = 1
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'visible_in_channel']:
                try:
                    visible = callable[2](u, localServer, user, channel)
                except Exception as ex:
                    logging.exception(ex)
                if not visible:
                    broadcast.remove(u)
                    logging.debug('/KICK: User {} is not allowed to see {} on channel {}'.format(u.nickname, user.nickname, channel.name))
                    break

        if type(self).__name__ == 'User':
            success = True
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'pre_local_kick']:
                try:
                    success = callable[2](self, localServer, user, channel, reason)
                    if not success and success is not None:
                        logging.debug('KICK denied by: {}'.format(callable))
                        break
                except Exception as ex:
                    logging.exception(ex)
            if not success and success is not None:
                return

        if oper_override:
            self.server.snotice('s', '*** OperOverride by {} ({}@{}) with KICK {} {} ({})'.format(self.nickname, self.ident, self.hostname, channel.name, user.nickname, reason))

        self.broadcast(broadcast, 'KICK {} {} :{}'.format(channel.name, user.nickname, reason))
        user.channels.remove(channel)
        channel.users.remove(user)
        channel.usermodes.pop(user)

        if len(channel.users) == 0 and 'P' not in channel.modes:
            localServer.channels.remove(channel)
            del localServer.chan_params[channel]
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'channel_destroy']:
                try:
                    callable[2](self, localServer, channel)
                except Exception as ex:
                    logging.exception(ex)

        for callable in [callable for callable in localServer.hooks if callable[0].lower() == hook]:
            try:
                callable[2](self, localServer, user, channel, reason)
            except Exception as ex:
                logging.exception(ex)

        if sync:
            localServer.new_sync(localServer, sourceServer, ':{} KICK {} {} :{}'.format(sourceID, channel.name, user.nickname, reason))

    except Exception as ex:
       logging.exception(ex)
