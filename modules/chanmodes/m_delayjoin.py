"""
provides chmode +D (delay join)
"""

import ircd

chmode = 'D'

from handle.functions import logging

can_see = {}

@ircd.Modules.req_modes('o')
@ircd.Modules.commands('delaydebug')
def debug(self, localServer, recv):
    global can_see
    chan = '#Home'
    chan_class = [c for c in localServer.channels if c.name.lower() == chan.lower()][0]
    if chan_class not in can_see:
        localServer.notice(self, '* State could not be found for {}'.format(chan_class))
        return
    localServer.notice(self, '*** State of {}:'.format(chan_class.name))
    localServer.notice(self, can_see[chan_class])

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes(chmode, 3, 4, 'Delay join message until the user speaks or receives channel status') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.hooks.pre_chanmsg()
def showjoin(self, localServer, channel, msg):
    if chmode in channel.modes:
        global can_see
        for user in [user for user in channel.users if self not in can_see[channel][user] and user != self]:
            logging.debug('/privmsg: Allowing visibility state for {} to {}'.format(self.nickname, user.nickname))
            data = ':{}!{}@{} JOIN {}{}'.format(self.nickname, self.ident, self.cloakhost, channel.name, ' {} :{}'.format(self.svid, self.realname) if 'extended-join' in user.caplist else '')
            user._send(data)
            can_see[channel][user].append(self)
    return msg

@ircd.Modules.hooks.visible_in_channel() ### Returns True or False depending if <user> should be visible on <channel> for <self>
def visible_in_chan(self, localServer, user, channel):
    global can_see
    if chmode not in channel.modes or (chmode in channel.modes and self.chlevel(channel) > 2 or user == self): # or ('o' in self.modes and user.chlevel(channel) <= 2)):
        if chmode in channel.modes and user not in can_see[channel][self]:
            can_see[channel][self].append(user)
        return 1
    if not can_see:
        return 1
    #if self in can_see[channel]:
    #    logging.debug('User {} can see the following users on {}: {}'.format(self.nickname, channel.name, can_see[channel][self]))
    if self in can_see[channel] and user in can_see[channel][self]:
        logging.debug('visible_in_chan() dict, returning 1')
        return 1
    return 0

@ircd.Modules.hooks.pre_local_join()
@ircd.Modules.hooks.pre_remote_join()
def hidejoin(self, localServer, channel, **kwargs):
    try:
        if chmode in channel.modes:
            global can_see
            if channel not in can_see:
                can_see[channel] = {}
                logging.debug('/JOIN: Channel {} added to can_see dict'.format(channel.name))
            if self not in can_see[channel]:
                can_see[channel][self] = []
            ### <self> just joined <channel>. They can see everyone currently on the channel.
            can_see[channel][self] = list(channel.users) ### /!\ Do NOT RE-ASSIGN the list. Make a copy! /!\
            for user in [user for user in channel.users if user != self]:
                if visible_in_chan(user, localServer, self, channel) and self not in can_see[channel][user]:
                    can_see[channel][user].append(self)
                    logging.debug('/join: User {} can see {}'.format(user.nickname, self.nickname))
        return (1, 0)
    except Exception as ex:
            logging.exception(ex)

@ircd.Modules.hooks.local_part()
@ircd.Modules.hooks.remote_part()
def hidepart(self, localServer, channel):
    if chmode in channel.modes:
        global can_see
        if channel not in can_see:
            logging.error('/PART: CRITICAL ERROR: channel {} is not found in the can_see dict!'.format(channel.name))
            return
        can_see[channel][self] = []
        for user in [user for user in channel.users if user in can_see[channel] and self in can_see[channel][user] and user.chlevel(channel) < 2]:
            logging.debug('/part: User {} can not see {} anymore.'.format(user.nickname, self.nickname))
            can_see[channel][user].remove(self)
        #logging.debug('/PART: current state for {}: {}'.format(channel.name, can_see[channel]))

@ircd.Modules.hooks.local_quit()
@ircd.Modules.hooks.remote_quit()
def hidequit(self, localServer):
    global can_see
    for channel in [chan for chan in self.channels if chmode in chan.modes]:
        del can_see[channel][self]
        for user in [user for user in channel.users if user in can_see[channel] and self in can_see[channel][user] and user.chlevel(channel) < 2]:
            logging.debug('/quit: User {} can not see {} anymore.'.format(user.nickname, self.nickname))
            can_see[channel][user].remove(self)
        #logging.debug('/QUIT: current state for {}: {}'.format(channel.name, can_see[channel]))

@ircd.Modules.hooks.modechar_add()
def set_D(localServer, self, channel, mode):
    if mode == chmode:
        if 'u' in channel.modes:
            localServer.notice(self, 'Mode +D cannot be set: channel has +u')
            return 0
        global can_see
        if channel not in can_see:
            can_see[channel] = {}

        for user1 in [u for u in channel.users if u not in can_see[channel]]:
            can_see[channel][user1] = []
            for user2 in [user2 for user2 in channel.users if user2 not in can_see[channel][user1]]:
                can_see[channel][user1].append(user2)
                logging.debug('Mode set, so user {} is visible to {}'.format(user2.nickname, user1.nickname))
    return 1

@ircd.Modules.hooks.modechar_del()
def unset_D(localServer, self, channel, mode):
    if mode == chmode:
        global can_see
        can_see = {}

@ircd.Modules.hooks.pre_local_chanmode()
@ircd.Modules.hooks.pre_remote_chanmode()
def chmode_D(self, localServer, channel, modebuf, parambuf, action, m, param):
    global can_see
    if m == chmode:
        if not hasattr(channel, 'delayjoins') or not channel.delayjoins:
            channel.delayjoins = []
        if action == '-':
            ### Show user joins to whoever needs them.
            for user in channel.users:
                for user2 in [user2 for user2 in channel.users if user2 not in can_see[channel][user] and user != user2]:
                    logging.debug('/MODE unset: Showing join from {} to {}'.format(user2.nickname, user.nickname))
                    data = ':{}!{}@{} JOIN {}{}'.format(user2.nickname, user2.ident, user2.cloakhost, channel.name, ' {} :{}'.format(user2.svid, user2.realname) if 'extended-join' in user.caplist else '')
                    user._send(data)
                    can_see[channel][user].append(user2)
            return

    if m not in localServer.chstatus or chmode not in channel.modes:
        return
    user = [user for user in channel.users if user.nickname == param or user.uid == param]
    if not user:
        return logging.error('No class found for {}{} param {}'.format(action, m, param))
    user = user[0]
    if action == '+' or action == '-':
        ### <user> should be visible to all users on <channel>
        logging.debug('/MODE: current state for {} {}: {}'.format(channel, user, can_see[channel][user]))
        for u in channel.users:
            ### Send JOIN to <u> if not already known.
            if user == u:
                continue
            if user not in can_see[channel][u]:
                logging.debug('/MODE: Show join {} from {} to {}'.format(channel.name, user.nickname, u.nickname))
                data = ':{}!{}@{} JOIN {}{}'.format(user.nickname, user.ident, user.cloakhost, channel.name, ' {} :{}'.format(user.svid, user.realname) if 'extended-join' in u.caplist else '')
                u._send(data)
                can_see[channel][u].append(user)

            ### Can <user> see <u> too?
            if user.chlevel(channel) > 2 and u not in can_see[channel][user]:
                ### Yes.
                logging.debug('/MODE2: Show join {} from {} to {}'.format(channel.name, u.nickname, user.nickname))
                data = ':{}!{}@{} JOIN {}{}'.format(u.nickname, u.ident, u.cloakhost, channel.name, ' {} :{}'.format(u.svid, u.realname) if 'extended-join' in user.caplist else '')
                user._send(data)
                can_see[channel][user].append(u)

        ###
        if action == '-': ### Not tested.
            for u in [u for u in channel.users if u != user]:
                logging.debug('User {} got status removed. Hiding {}?'.format(user.nickname, u.nickname))
                if user.chlevel(channel) < 3 and u in can_see[channel][user]:
                    ### Hide <u> from <user>
                    u.broadcast([user], 'PART :{}'.format(channel.name))
                    can_see[channel][user].remove(u)


@ircd.Modules.hooks.local_kick()
@ircd.Modules.hooks.remote_kick()
def hide_kick(self, localServer, user, channel, reason):
    if chmode in channel.modes:
        global can_see
        if channel not in can_see:
            logging.error('/KICK: CRITICAL ERROR: channel {} is not found in the can_see dict!'.format(channel.name))
            return
        can_see[channel][user] = []
        for u in [u for u in channel.users if u in can_see[channel] and user in can_see[channel][u]]:
            logging.debug('/kick: User {} can not see {} anymore.'.format(u.nickname, user.nickname))
            can_see[channel][u].remove(user)

def init(self, reload=False):
    global can_see
    if can_see or reload:
        return
    can_see = {}
    for chan in self.channels:
        if chan not in can_see:
            can_see[chan] = {}
            logging.debug('INIT: Channel {} added to can_see dict'.format(chan.name))
        for user in [user for user in chan.users if user not in can_see[chan]]:
            can_see[chan][user] = []

def unload(self):
    global can_see
    for channel in [channel for channel in self.channels if hasattr(channel, 'delayjoins') and channel in can_see]:
        if not hasattr(channel, 'delayjoins') or not channel.delayjoins:
            channel.delayjoins = []
        ### Show user joins to whoever needs them.
        for user in channel.users:
            for user2 in [user2 for user2 in channel.users if user2 not in can_see[channel][user]]:
                logging.debug('Module unload: Showing join from {} to {}'.format(user2, user))
                data = ':{}!{}@{} JOIN {}{}'.format(user2.nickname, user2.ident, user2.cloakhost, channel.name, ' {} :{}'.format(user2.svid, user2.realname) if 'extended-join' in user.caplist else '')
                user._send(data)
                can_see[channel][user].append(user2)

    can_see = {}
