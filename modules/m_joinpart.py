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


def init(ircd, reload=False):
    ### Other modules also require this information, like /privmsg and /notice
    ircd.chantypes = chantypes


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



class Join(ircd.Command):
    """
    Syntax: JOIN <channel> [key]
    Joins a given channel with optional [key].
    """
    def __init__(self):
        self.command = 'join'
        self.params = 1
        self.support = [('CHANTYPES', str(chantypes)), ('CHANNELLEN', str(chanlen))]


    def execute(self, client, recv, override=False, skipmod=None, sourceServer=None):
        hook = 'local_join'
        if type(client).__name__ == 'Server':
            if not sourceServer:
                sourceServer = client
            S = recv[0][1:]
            recv = recv[1:]
            override = True
            hook = 'remote_join'
            logging.warning('Remote JOIN received instead of SJOIN')
        elif not sourceServer:
            sourceServer = client.server

        if recv[1] == '0':
            for channel in list(client.channels):
                client.handle('PART {} :Left all channels'.format(channel.name))
            return

        pc = 0
        key = None
        for chan in recv[1].split(',')[:12]:
            if int(time.time()) - client.signon > 5:
                client.flood_penalty += 10000
            regex = re.compile('\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?', re.UNICODE)
            chan = regex.sub('', chan).strip()
            channel = [c for c in self.ircd.channels if c.name.lower() == chan.lower()]
            if channel and client in channel[0].users or not chan:
                continue

            #if len(chan) == 1 and not override:
            #    continue

            continueLoop = False
            valid = "abcdefghijklmnopqrstuvwxyz0123456789`~!@#$%^&*()-=_+[]{}\\|;':\"./<>?"

            for c in chan:
                if c.lower() not in valid and (sourceServer == self.ircd and not channel):
                    client.sendraw(479, '{} :Illegal channel name'.format(chan))
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

            if chan[0] not in chantypes and recv[0] != '0' and (sourceServer == self.ircd and not channel) or chan in chantypes:
                client.sendraw(403, '{} :Invalid channel name'.format(chan))
                continue

            if len(chan) > chanlen and (sourceServer == self.ircd and not channel):
                client.sendraw(485, '{} :Channel too long'.format(chan))
                continue

            if not channel:
                if 'onlyopersjoin' in self.ircd.conf['settings'] and self.ircd.conf['settings']['onlyopersjoin'] and 'o' not in client.modes and client.server == self.ircd:
                    self.ircd.notice(client, '*** Channel creation is limited to IRC operators.')
                    continue
                new = Channel(chan)
                logging.debug('New channel instance created: {}'.format(new))
                self.ircd.channels.append(new)
                channel = [new]
                for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'channel_create']:
                    try:
                        callable[2](client, self.ircd, channel[0])
                    except Exception as ex:
                        logging.error('Exception in {}:'.format(callable))
                        logging.exception(ex)

            channel = channel[0]

            invite_override = False
            if client in channel.invites:
                invite_override = channel.invites[client]['override']

            ### Check for module hooks.
            if type(client).__name__ == 'User':
                success = True
                overrides = []
                kwargs = {}
                if override:
                    kwargs['override'] = True
                for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'pre_'+hook and callable[3] != skipmod]:
                    try:
                        success, overrides = callable[2](client, self.ircd, channel, **kwargs)
                        if not success:
                            logging.debug('Join denied for {} to {} :: source {}'.format(client.nickname, channel.name, callable))
                            break
                    except Exception as ex:
                        logging.error('Exception in {}:'.format(callable))
                        logging.exception(ex)
                if not success:
                    continue

            if not override:
                if 'O' in channel.modes and 'o' not in client.modes:
                    client.sendraw(520, '{} :Cannot join channel (IRCops only)'.format(channel.name))
                    continue

                if 'R' in channel.modes and 'r' not in client.modes and not invite_override:
                    client.sendraw(477, '{} :You need a registered nick to join that channel'.format(channel.name))
                    if channel.redirect:
                        client.handle('JOIN', channel.redirect)
                        client.sendraw(471, '{} :Channel is +R so you are redirected to {}'.format(channel.name, channel.redirect))
                        continue
                    continue

                if 'z' in channel.modes and 'z' not in client.modes and not invite_override:
                    client.sendraw(489, '{} :Cannot join channel (not using a secure connection)'.format(channel.name))
                    if channel.redirect:
                        client.handle('JOIN', channel.redirect)
                        client.sendraw(471, '{} :Channel is +z so you are redirected to {}'.format(channel.name, channel.redirect))
                        continue
                    continue

                if checkMatch(client, self.ircd, 'b', channel) and not checkMatch(client, self.ircd, 'e', channel) and not invite_override and 'b' not in overrides:
                    client.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    if channel.redirect:
                        client.handle('JOIN', channel.redirect)
                        client.sendraw(471, '{} :You arae banned so you are redirected to {}'.format(channel.name, channel.redirect))
                        continue
                    continue

                #if channel.limit != 0 and len(channel.users) >= channel.limit and not invite_override:
                #print(channel.modes)
                if 'l' in channel.modes and len(channel.users) >= int(self.ircd.chan_params[channel]['l']) and not invite_override:
                    if 'L' in channel.modes:
                        redirect_chan = self.ircd.chan_params[channel]['L']
                        client.handle('JOIN', redirect_chan)
                        client.sendraw(471, '{} :Channel is full so you are redirected to {}'.format(channel.name, redirect_chan))
                        continue

                    client.sendraw(471, '{} :Cannot join channel (+l)'.format(channel.name))
                    continue

                #if channel.key and key != channel.key and not invite_override:
                if 'k' in channel.modes and key != self.ircd.chan_params[channel]['k'] and not invite_override:
                    ### Check key based on modes that require params.
                    client.sendraw(475, '{} :Cannot join channel (+k)'.format(channel.name))
                    continue

                if 'i' in channel.modes and client not in channel.invites and not checkMatch(client, self.ircd, 'I', channel) and not invite_override and 'i' not in overrides:
                    client.sendraw(473, '{} :Cannot join channel (+i)'.format(channel.name))
                    continue

            logging.info('Joining {} in {}'.format(client, channel))
            if not channel.users and channel not in self.ircd.chan_params:
                self.ircd.chan_params[channel] = {}
            if not channel.users and (client.server.eos or client.server == self.ircd) and channel.name[0] != '+':
                channel.usermodes[client] = 'o'
            else:
                channel.usermodes[client] = ''

            channel.users.append(client)
            client.channels.append(channel)
            if client in channel.invites:
                del channel.invites[client]

            broadcast = list(channel.users)
            ### Check module hooks for visible_in_channel()
            for u in [u for u in broadcast if u != client]:
                visible = 1
                for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'visible_in_channel']:
                    try:
                        visible = callable[2](u, self.ircd, client, channel)
                        #logging.debug('/JOIN: Can {} see {} ? :: {}'.format(u, client, visible))
                    except Exception as ex:
                        logging.exception(ex)
                    if not visible:
                        broadcast.remove(u)
                        logging.debug('Join of {} hidden from {} in {}'.format(client.nickname, u.nickname, channel.name))
                        logging.debug('{} returned {}'.format(callable, visible))
                        break

            #print('Broadcasting join to: {}'.format(broadcast))
            for user in broadcast:
                data = ':{}!{}@{} JOIN {}{}'.format(client.nickname, client.ident, client.cloakhost, channel.name, ' {} :{}'.format(client.svid, client.realname) if 'extended-join' in user.caplist else '')
                user._send(data)

            if channel.topic_time != 0:
                client.handle('TOPIC', channel.name)
            p = {'flood_safe': True}
            client.handle('NAMES', channel.name, params=p)

            prefix = ''
            for mode in [mode for mode in self.ircd.chprefix if mode in channel.usermodes[client]]:
                prefix += self.ircd.chprefix[mode]

            if channel.name[0] != '&' and (sourceServer.eos or sourceServer == self.ircd):
                data = ':{} SJOIN {} {}{} :{}{}'.format(sourceServer.sid, channel.creation, channel.name, ' +{}'.format(channel.modes) if channel.modes and channel.users == [client] else '', prefix, client.uid)
                self.ircd.new_sync(self.ircd, sourceServer, data)

            if channel.users == [client] and channel.name[0] != '+':
                sourceServer.handle('MODE', '{} +nt'.format(channel.name))

            for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == hook and callable[3] != skipmod]:
                try:
                    callable[2](client, self.ircd, channel)
                except Exception as ex:
                    logging.exception(ex)



class Part(ircd.Command):
    """
    Syntax: PART <channel> [reason]
    Parts the given channel with optional [reason].
    """

    def __init__(self):
        self.command = 'part'
        self.ircd = ircd


    def execute(self, client, recv, reason=None):
        if type(client).__name__ == 'Server':
            hook = 'remote_part'
            sourceServer = client
            client = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], self.ircd.users))[0]
            recv = recv[1:]
        else:
            hook = 'local_part'
            sourceServer = client.server

        if not reason:
            if len(recv) > 2:
                reason = ' '.join(recv[2:])
                if reason.startswith(':'):
                    reason = reason[1:]
                reason = ':{}'.format(reason)
            else:
                reason = ''

            reason = reason.rstrip()

        if 'static-part' in self.ircd.conf['settings'] and self.ircd.conf['settings']['static-part']:
            reason = self.ircd.conf['settings']['static-part']

        for chan in recv[1].split(','):
            if int(time.time()) - client.signon > 5:
                client.flood_penalty += 10000
            channel = list(filter(lambda c: c.name.lower() == chan.lower(), self.ircd.channels))
            if not channel or client not in channel[0].users:
                client.sendraw(442, '{} :You\'re not on that channel'.format(chan))
                continue

            channel = channel[0]

            client.channels.remove(channel)
            channel.usermodes.pop(client)
            channel.users.remove(client)

            broadcast = list(channel.users)+[client]
            ### Check module hooks for visible_in_channel()
            for u in [u for u in broadcast if u != client]:
                visible = 1
                for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'visible_in_channel']:
                    try:
                        visible = callable[2](u, self.ircd, client, channel)
                        #logging.debug('/PART: Can {} see {} ? :: {}'.format(u, client, visible))
                    except Exception as ex:
                        logging.exception(ex)
                    if not visible:
                        broadcast.remove(u)
                        logging.debug('Part of {} hidden from {} in {}'.format(client.nickname, u.nickname, channel.name))
                        logging.debug('{} returned {}'.format(callable, visible))
                        break

            client.broadcast(broadcast, 'PART {} {}'.format(channel.name, reason))
            for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'pre_local_part']:
                try:
                    callable[2](client, self.ircd, channel)
                except Exception as ex:
                    logging.exception(ex)
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
                    callable[2](client, self.ircd, channel)
                except Exception as ex:
                    logging.exception(ex)

            if channel.name[0] != '&':
                self.ircd.new_sync(self.ircd, sourceServer, ':{} PART {} {}'.format(client.uid, channel.name, reason))
