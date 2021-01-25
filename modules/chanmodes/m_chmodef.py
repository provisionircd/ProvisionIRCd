"""
provides chmode +f (flood control)
"""

import time

import ircd
from handle.functions import logging

defAction = {
    'm': 'kick',
    'j': 'i'
}

chmode = "f"

info = """Format:     +f [amount:type:secs][action:duration] --- duration is in minutes.
-
Example:    +f 3:j:10 (3 join in 10 sec, default is +i for 1 minute)
Example:    +f 3:j:10:i:2 (3 joins in 10 sec, sets channel to +i for 2 minutes)
Example:    +f 3:j:10:R:5 (3 joins in 10 sec, sets channel to +R for 5 minutes)
-
Example:    +f 3:m:10 (3 messages in 10 sec, default action is kick)
Example:    +f 5:m:3:b:1 (5 messages in 3 sec, will ban/kick for 1 minute)
Example:    +f 10:m:5:m:2 (10 messages in 5 sec, will set +m for 2 minutes)
"""

helpop = {"chmodef": info}


@ircd.Modules.hooks.loop()
def checkExpiredFloods(ircd):
    ### Checking for timed-out flood protection.
    channels = (channel for channel in ircd.channels if chmode in channel.modes and 'm' in channel.chmodef)
    for chan in channels:
        if chan.chmodef['m']['action'] == 'm' and 'm' in chan.modes:
            if chan.chmodef['m']['actionSet'] and int(time.time()) - chan.chmodef['m']['actionSet'] > chan.chmodef['m']['duration'] * 60:
                ircd.handle('MODE', '{} -m'.format(chan.name))
                chan.chmodef['m']['actionSet'] = None

        for user in (user for user in chan.users if user in dict(chan.messageQueue)):
            if time.time() - chan.messageQueue[user]['ctime'] > chan.chmodef['m']['time']:
                # print('Resetting flood for {} on {}'.format(user,chan))
                del chan.messageQueue[user]

    channels = (channel for channel in ircd.channels if chmode in channel.modes and 'j' in channel.chmodef)
    for chan in channels:
        for entry in (entry for entry in dict(chan.joinQueue)):
            if int(time.time()) - chan.joinQueue[entry]['ctime'] > chan.chmodef['j']['time']:
                # print('Resetting flood for {} on {}'.format(user, chan))
                del chan.joinQueue[entry]
        if chan.chmodef['j']['action'] == 'i' and 'i' in chan.modes:
            if chan.chmodef['j']['actionSet'] and int(time.time()) - chan.chmodef['j']['actionSet'] > chan.chmodef['j']['duration'] * 60:
                ircd.handle('MODE', '{} -i'.format(chan.name))
                chan.chmodef['j']['actionSet'] = None
        elif chan.chmodef['j']['action'] == 'R' and 'R' in chan.modes:
            if chan.chmodef['j']['actionSet'] and int(time.time()) - chan.chmodef['j']['actionSet'] > chan.chmodef['j']['duration'] * 60:
                ircd.handle('MODE', '{} -R'.format(chan.name))
                chan.chmodef['j']['actionSet'] = None


@ircd.Modules.hooks.chanmsg()
def msg(self, ircd, channel, msg):
    if chmode in channel.modes and 'm' in channel.chmodef and self.chlevel(channel) < 2 and 'o' not in self.modes:
        if self not in channel.messageQueue:
            channel.messageQueue[self] = {}
            channel.messageQueue[self]['ctime'] = time.time()
        channel.messageQueue[self][int(round(time.time() * 1000))] = None
        if len(channel.messageQueue[self]) > channel.chmodef['m']['amount']:
            p = {'sync': False}
            if channel.chmodef['m']['action'] == 'kick':
                ircd.handle('KICK', '{} {} :Flood! Limit is {} messages in {} seconds.'.format(channel.name, self.uid, channel.chmodef['m']['amount'], channel.chmodef['m']['time']), params=p)
            elif channel.chmodef['m']['action'] == 'b':
                duration = channel.chmodef['m']['duration']
                ircd.handle('MODE', '{} +b ~t:{}:*@{}'.format(channel.name, duration, self.cloakhost))
                ircd.handle('KICK', '{} {} :Flood! Limit is {} messages in {} seconds.'.format(channel.name, self.uid, channel.chmodef['m']['amount'], channel.chmodef['m']['time']), params=p)
            elif channel.chmodef['m']['action'] == 'm':
                ircd.handle('MODE', '{} +m'.format(channel.name))
                channel.chmodef['m']['actionSet'] = int(time.time())
            del channel.messageQueue[self]


@ircd.Modules.hooks.channel_create()
@ircd.Modules.hooks.channel_destroy()
def chmodef_dictset(self, ircd, channel):
    channel.chmodef = {}
    channel.messageQueue = {}
    channel.joinQueue = {}


@ircd.Modules.hooks.local_join()
def join(self, ircd, channel):
    if chmode in channel.modes and 'j' in channel.chmodef and not self.ocheck('o', 'override') and self.server.eos:
        r = int(round(time.time() * 1000))
        channel.joinQueue[r] = {}
        channel.joinQueue[r]['ctime'] = int(time.time())
        if len(channel.joinQueue) > channel.chmodef['j']['amount']:
            channel.joinQueue = {}
            if channel.chmodef['j']['action'] == 'i':
                ircd.handle('MODE', '{} +i'.format(channel.name))
            elif channel.chmodef['j']['action'] == 'R':
                ircd.handle('MODE', '{} +R'.format(channel.name))
            channel.chmodef['j']['actionSet'] = int(time.time())


@ircd.Modules.hooks.modechar_del()
def mode_del(ircd, self, channel, mode):
    if mode == chmode:
        channel.chmodef = {}
    if mode == 'i':
        channel.joinQueue = {}
    if mode == 'm':
        channel.messageQueue = {}


@ircd.Modules.channel_mode
class chmodef(ircd.ChannelMode):
    def __init__(self):
        self.mode = 'f'
        self.desc = 'Set flood protection for your channel (/helpop chmodef for more info)'
        self.type = 2


### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
# @ircd.Modules.channel_modes(chmode, 2, 3, 'Set flood protection for your channel (/helpop chmodef for more info)', None, None, '[params]') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.hooks.pre_local_chanmode(chmode)
@ircd.Modules.hooks.pre_remote_chanmode(chmode)
def addmode_f(self, ircd, channel, modebuf, parambuf, action, modebar, param):
    try:
        floodTypes = 'jm'
        tempparam = []
        if action == '-':
            return 1
        for p in param.split(','):
            if len(p) < 2:
                return 0
            if p[0] == '-':
                type = p[1]
                # logging.debug('Removing flood type: ', type)
                if type not in floodTypes or type not in channel.chmodef:
                    logging.debug('Type {} not found in {}'.format(type, channel.chmodef))
                    return 0
                del channel.chmodef[type]
                # logging.debug('Success! Returning {}'.format(type))
                if len(channel.chmodef) == 0:
                    logging.debug(f'No more protections set. Removing "{chmode}" completely.')
                    self.handle('MODE', '{} -{}'.format(channel.name, chmode))
                    return 0

                p = []
                for t in channel.chmodef:
                    p.append('{}:{}:{}'.format(channel.chmodef[t]['amount'], t, channel.chmodef[t]['time']))
                ircd.chan_params[channel][m] = ','.join(p)
                return 0

            if len(p.split(':')) < 3:
                return 0
            if not p.split(':')[0].isdigit():
                return 0
            if p.split(':')[1] not in floodTypes:
                return 0
            if not p.split(':')[2].isdigit():
                return 0

            duration = 1
            type = p.split(':')[1]
            fAction = defAction[type]
            try:
                fAction = p.split(':')[3]
            except:
                pass
            try:
                duration = int(p.split(':')[4])
            except:
                pass
            amount = int(p.split(':')[0])
            secs = int(p.split(':')[2])
            if chmode in channel.modes and type in channel.chmodef:
                logging.debug('Updating current protection from {}'.format(channel.chmodef))
                if amount == channel.chmodef[type]['amount'] and secs == channel.chmodef[type]['time'] and fAction == channel.chmodef[type]['action'] and duration == channel.chmodef[type]['duration']:
                    return 0
                del channel.chmodef[type]
            if fAction:
                if type == 'm' and fAction not in ['m', 'b']:
                    ### Invalid action, reverting to default.
                    fAction = None
                elif type == 'j' and fAction not in ['i', 'R']:
                    ### Invalid action, reverting to default.
                    fAction = None
                if fAction:
                    try:
                        duration = p.split(':')[4]
                        if not duration.isdigit():
                            # logging.debug('Invalid duration "{}" unsetting action'.format(duration))
                            fAction = None
                        else:
                            duration = int(duration)
                            # logging.debug('Duration for {} set to: {}'.format(fAction, duration))
                    except Exception as ex:
                        # logging.debug('Alternative action was given, but no duration. Unsetting action')
                        fAction = None

            channel.chmodef[type] = {}
            channel.chmodef[type]['amount'] = amount
            channel.chmodef[type]['time'] = secs
            channel.chmodef[type]['duration'] = duration
            if not fAction:
                p = ':'.join(p.split(':')[:3])
                ### Default action
                if type == 'm':
                    channel.chmodef[type]['action'] = 'kick'
                elif type == 'j':
                    channel.chmodef[type]['action'] = 'i'
                    channel.chmodef[type]['actionSet'] = None

            else:
                channel.chmodef[type]['action'] = str(fAction)
                channel.chmodef[type]['actionSet'] = None

            tempparam.append(p)

            p = []
            for t in channel.chmodef:
                p.append('{}:{}:{}'.format(channel.chmodef[t]['amount'], t, channel.chmodef[t]['time']))
            ircd.chan_params[channel][chmode] = ','.join(p)

            if len(tempparam) == 1 and chmode not in modebuf:
                modebuf.append(chmode)

        if tempparam and ','.join(tempparam) not in parambuf:
            parambuf.append(','.join(tempparam))

    except Exception as ex:
        logging.exception(ex)


def init(ircd, reload=False):
    for chan in [chan for chan in ircd.channels if not hasattr(chan, 'chmodef')]:
        chan.chmodef = {}
    for chan in [chan for chan in ircd.channels if not hasattr(chan, 'messageQueue')]:
        chan.messageQueue = {}
    for chan in [chan for chan in ircd.channels if not hasattr(chan, 'joinQueue')]:
        chan.joinQueue = {}
