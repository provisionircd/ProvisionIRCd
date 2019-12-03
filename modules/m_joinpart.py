"""
commands /join and /part
"""

import ircd

Channel = ircd.Channel

from handle.functions import match, logging
import time
import re

chantypes = '#+&'
chanlen = 36

def init(localServer, reload=False):
    ### Other modules also require this information, like /privmsg and /notice
    localServer.chantypes = chantypes

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
R2 = '\033[91m' # bright red
G = '\033[32m' # green
G2 = '\033[92m' # bright green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

matches = {}
matches['b'] = 'bans'
matches['e'] = 'excepts'
matches['I'] = 'invex'
def checkMatch(self, localServer, type, channel):
    if type not in matches or not hasattr(channel, matches[type]):
        return
    for b in getattr(channel, matches[type]):
        if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
            return 1
        if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
            return 1
        if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
            return 1

@ircd.Modules.params(1)
@ircd.Modules.support('CHANTYPES='+str(chantypes))
@ircd.Modules.support('CHANNELLEN='+str(chanlen))
@ircd.Modules.commands('join')
def join(self, localServer, recv, override=False, skipmod=None, sourceServer=None):
    """Syntax: JOIN <channel> [key]
Joins a given channel with optional [key]."""
    try:
        hook = 'local_join'
        if type(self).__name__ == 'Server':
            if not sourceServer:
                sourceServer = self
            S = recv[0][1:]
            #source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
            #self = source[0]
            recv = recv[1:]
            override = True
            hook = 'remote_join'
            logging.warning('Remote JOIN received instead of SJOIN')
        elif not sourceServer:
            sourceServer = self.server

        if recv[1] == '0':
            for channel in list(self.channels):
                self.handle('PART {} :Left all channels'.format(channel.name))
            return

        pc = 0
        key = None
        for chan in recv[1].split(',')[:12]:
            if int(time.time()) - self.signon > 5:
                self.flood_penalty += 10000
            regex = re.compile('\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?', re.UNICODE)
            chan = regex.sub('', chan).strip()
            channel = [c for c in localServer.channels if c.name.lower() == chan.lower()]
            if channel and self in channel[0].users or not chan:
                continue

            if len(chan) == 1 and not override:
                continue

            continueLoop = False
            valid = "abcdefghijklmnopqrstuvwxyz0123456789`~!@#$%^&*()-=_+[]{}\\|;':\"./<>?"

            for c in chan:
                if c.lower() not in valid and (sourceServer == localServer and not channel):
                    self.sendraw(479, '{} :Illegal channel name'.format(chan))
                    continueLoop = True
                    break
            if continueLoop:
                continue
            ### This key-check can be improved. Check which modes require params, and increase accordingly.
            if len(recv) > 2:
                try:
                    key = recv[2:][pc]
                    pc += 1
                except:
                    pass

            if chan[0] not in chantypes and recv[0] != '0' and (sourceServer == localServer and not channel):
                self.sendraw(403, '{} :Invalid channel name'.format(chan))
                continue

            if len(chan) > chanlen and (sourceServer == localServer and not channel):
                self.sendraw(485, '{} :Channel too long'.format(chan))
                continue

            if not channel:
                if 'onlyopersjoin' in localServer.conf['settings'] and localServer.conf['settings']['onlyopersjoin'] and 'o' not in self.modes and self.server == localServer:
                    localServer.notice(self, '*** Channel creation is limited to IRC operators.')
                    continue
                new = Channel(chan)
                logging.debug('New channel instance created: {}'.format(new))
                localServer.channels.append(new)
                channel = [new]
                for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'channel_create']:
                    try:
                        callable[2](self, localServer, channel[0])
                    except Exception as ex:
                        logging.error('Exception in {}:'.format(callable))
                        logging.exception(ex)

            channel = channel[0]

            invite_override = False
            if self in channel.invites:
                invite_override = channel.invites[self]['override']

            ### Check for module hooks.
            if type(self).__name__ == 'User':
                success = True
                overrides = []
                kwargs = {}
                if override:
                    kwargs['override'] = True
                for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'pre_'+hook and callable[3] != skipmod]:
                    try:
                        success, overrides = callable[2](self, localServer, channel, **kwargs)
                        if not success:
                            logging.debug('Join denied for {} {} by module {}'.format(self, channel, callable))
                            break
                    except Exception as ex:
                        logging.error('Exception in {}:'.format(callable))
                        logging.exception(ex)
                if not success:
                    continue

            if not override:
                if 'O' in channel.modes and 'o' not in self.modes:
                    self.sendraw(520, '{} :Cannot join channel (IRCops only)'.format(channel.name))
                    continue

                if 'R' in channel.modes and 'r' not in self.modes and not invite_override:
                    self.sendraw(477, '{} :You need a registered nick to join that channel'.format(channel.name))
                    if channel.redirect:
                        self.handle('JOIN', channel.redirect)
                        self.sendraw(471, '{} :Channel is +R so you are redirected to {}'.format(channel.name, channel.redirect))
                        continue
                    continue

                if 'z' in channel.modes and 'z' not in self.modes and not invite_override:
                    self.sendraw(489, '{} :Cannot join channel (not using a secure connection)'.format(channel.name))
                    if channel.redirect:
                        self.handle('JOIN', channel.redirect)
                        self.sendraw(471, '{} :Channel is +z so you are redirected to {}'.format(channel.name, channel.redirect))
                        continue
                    continue

                if checkMatch(self, localServer, 'b', channel) and not checkMatch(self, localServer, 'e', channel) and not invite_override and 'b' not in overrides:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    if channel.redirect:
                        self.handle('JOIN', channel.redirect)
                        self.sendraw(471, '{} :You arae banned so you are redirected to {}'.format(channel.name, channel.redirect))
                        continue
                    continue

                #if channel.limit != 0 and len(channel.users) >= channel.limit and not invite_override:
                #print(channel.modes)
                if 'l' in channel.modes and len(channel.users) >= int(localServer.chan_params[channel]['l']) and not invite_override:
                    if channel.redirect:
                        self.handle('JOIN', channel.redirect)
                        self.sendraw(471, '{} :Channel is full so you are redirected to {}'.format(channel.name, channel.redirect))
                        continue

                    self.sendraw(471, '{} :Cannot join channel (+l)'.format(channel.name))
                    continue

                #if channel.key and key != channel.key and not invite_override:
                if 'k' in channel.modes and key != localServer.chan_params[channel]['k'] and not invite_override:
                    ### Check key based on modes that require params.
                    self.sendraw(475, '{} :Cannot join channel (+k)'.format(channel.name))
                    continue

                if 'i' in channel.modes and self not in channel.invites and not checkMatch(self, localServer, 'I', channel) and not invite_override and 'i' not in overrides:
                    self.sendraw(473, '{} :Cannot join channel (+i)'.format(channel.name))
                    continue

            logging.info('Joining {} in {}'.format(self, channel))
            if not channel.users and channel not in localServer.chan_params:
                localServer.chan_params[channel] = {}
            if not channel.users and (self.server.eos or self.server == localServer) and channel.name[0] != '+':
                channel.usermodes[self] = 'o'
            else:
                channel.usermodes[self] = ''

            channel.users.append(self)
            self.channels.append(channel)
            if self in channel.invites:
                del channel.invites[self]

            broadcast = list(channel.users)
            ### Check module hooks for visible_in_channel()
            for u in [u for u in broadcast if u != self]:
                visible = 1
                for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'visible_in_channel']:
                    try:
                        visible = callable[2](u, localServer, self, channel)
                        #logging.debug('/JOIN: Can {} see {} ? :: {}'.format(u, self, visible))
                    except Exception as ex:
                        logging.exception(ex)
                    if not visible:
                        broadcast.remove(u)
                        logging.debug('Join of {} hidden from {} in {}'.format(self.nickname, u.nickname, channel.name))
                        logging.debug('{} returned {}'.format(callable, visible))
                        break

            #print('Broadcasting join to: {}'.format(broadcast))
            for user in broadcast:
                data = ':{}!{}@{} JOIN {}{}'.format(self.nickname, self.ident, self.cloakhost, channel.name, ' {} :{}'.format(self.svid, self.realname) if 'extended-join' in user.caplist else '')
                user._send(data)

            if channel.topic_time != 0:
                self.handle('TOPIC', channel.name)
            p = {'flood_safe': True}
            self.handle('NAMES', channel.name, params=p)

            prefix = ''
            for mode in [mode for mode in localServer.chprefix if mode in channel.usermodes[self]]:
                prefix += localServer.chprefix[mode]

            if channel.name[0] != '&' and (sourceServer.eos or sourceServer == localServer):
                data = ':{} SJOIN {} {}{} :{}{}'.format(sourceServer.sid, channel.creation, channel.name, ' +{}'.format(channel.modes) if channel.modes and channel.users == [self] else '', prefix, self.uid)
                localServer.new_sync(localServer, sourceServer, data)

            if channel.users == [self] and channel.name[0] != '+':
                sourceServer.handle('MODE', '{} +nt'.format(channel.name))

            for callable in [callable for callable in localServer.hooks if callable[0].lower() == hook and callable[3] != skipmod]:
                try:
                    callable[2](self, localServer, channel)
                except Exception as ex:
                    logging.exception(ex)
    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.params(1)
@ircd.Modules.commands('part')
def part(self, localServer, recv, reason=None):
    """Syntax: PART <channel> [reason]
Parts the given channel with optional [reason]."""
    try:
        if type(self).__name__ == 'Server':
            hook = 'remote_part'
            sourceServer = self
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
            recv = recv[1:]
        else:
            hook = 'local_part'
            sourceServer = self.server

        if not reason:
            if len(recv) > 2:
                reason = ' '.join(recv[2:])
                if reason.startswith(':'):
                    reason = reason[1:]
                reason = ':{}'.format(reason)
            else:
                reason = ''

            reason = reason.rstrip()

        if 'static-part' in localServer.conf['settings'] and localServer.conf['settings']['static-part']:
            reason = localServer.conf['settings']['static-part']

        for chan in recv[1].split(','):
            if int(time.time()) - self.signon > 5:
                self.flood_penalty += 10000
            channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))
            if not channel or self not in channel[0].users:
                self.sendraw(442, '{} :You\'re not on that channel'.format(chan))
                continue

            channel = channel[0]

            self.channels.remove(channel)
            channel.usermodes.pop(self)
            channel.users.remove(self)

            broadcast = list(channel.users)+[self]
            ### Check module hooks for visible_in_channel()
            for u in [u for u in broadcast if u != self]:
                visible = 1
                for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'visible_in_channel']:
                    try:
                        visible = callable[2](u, localServer, self, channel)
                        #logging.debug('/PART: Can {} see {} ? :: {}'.format(u, self, visible))
                    except Exception as ex:
                        logging.exception(ex)
                    if not visible:
                        broadcast.remove(u)
                        logging.debug('Part of {} hidden from {} in {}'.format(self.nickname, u.nickname, channel.name))
                        logging.debug('{} returned {}'.format(callable, visible))
                        break

            self.broadcast(broadcast, 'PART {} {}'.format(channel.name, reason))
            for callable in [callable for callable in localServer.hooks if callable[0].lower() == 'pre_local_part']:
                try:
                    callable[2](self, localServer, channel)
                except Exception as ex:
                    logging.exception(ex)
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
                    callable[2](self, localServer, channel)
                except Exception as ex:
                    logging.exception(ex)

            if channel.name[0] != '&':
                localServer.new_sync(localServer, sourceServer, ':{} PART {} {}'.format(self.uid, channel.name, reason))

    except Exception as ex:
        logging.exception(ex)
