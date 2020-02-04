"""
/mode command
"""

import ircd

import os
import importlib
import sys
import time
import re
import json

from handle.functions import valid_expire, match, cloak, logging, save_db
from collections import OrderedDict

#W  = '\033[0m'  # white (normal)
#R  = '\033[31m' # red
#G  = '\033[32m' # green
#Y  = '\033[33m' # yellow
#B  = '\033[34m' # blue
#P  = '\033[35m' # purple

### Make these global so they can be modified by modules.
commandQueue = []
modebuf = []
parambuf = []

MAXMODES = 24

def makeMask(ircd, data):
    if not data:
        return
    nick, ident, host = '', '', ''
    nick = data.split('!')[0]
    if nick == '' or '@' in nick or ('.' in nick and '@' not in data):
        nick = '*'
    if len(nick) > ircd.nicklen:
        nick = '*{}'.format(nick[-20:])
    try:
        if '@' in data:
            ident = data.split('@')[0]
            if '!' in ident:
                ident = data.split('@')[0].split('!')[1]
        else:
            ident = data.split('!')[1].split('@')[0]
    except:
        ident = '*'
    if ident == '':
        ident = '*'
    if len(ident) > 12:
        ident = '*{}'.format(ident[-12:])
    try:
        host = data.split('@')[1]
    except:
        if '.' in data:
            try:
                host = ''.join(data.split('@'))
            except:
                host = '*'
    if len(host) > 64:
        host = '*{}'.format(host[-64:])
    if host == '':
        host = '*'
    result = '{}!{}@{}'.format(nick, ident, host)
    return result


oper_override = False
def processModes(self, ircd, channel, recv, sync=True, sourceServer=None, sourceUser=None):
    logging.debug('processModes(): {} :: {}'.format(self, recv))
    try:
        if sourceServer != ircd or (type(sourceUser).__name__ == 'User' and sourceUser.server != ircd):
            hook = 'remote_chanmode'
        else:
            hook = 'local_chanmode'
        rawModes = ' '.join(recv[1:])
        if rawModes.startswith(':'):
            rawModes = rawModes[1:]
        if type(sourceUser).__name__ == 'User':
            displaySource = sourceUser.uid
        else:
            displaySource = sourceUser.sid
            #if not sourceServer.eos and sourceServer != ircd:
            #    sync = False
    except Exception as ex:
        logging.exception(ex)
    try:
        global modebuf, parambuf, action, prevaction, commandQueue
        modebuf, parambuf, commandQueue = [], [], []
        action = ''
        prevaction = ''
        paramcount = -1
        chmodes = ircd.chstatus
        ircd.parammodes = ircd.chstatus
        for x in range(0, 4):
            for m in [m for m in ircd.channel_modes[x] if m not in chmodes]:
                chmodes += m
                if str(x) in '012' and m not in ircd.parammodes:
                    ircd.parammodes += m

        global oper_override
        extban_prefix = None
        if 'EXTBAN' in ircd.support:
            extban_prefix = ircd.support['EXTBAN'][0]
            #logging.info('Extban prefix set: {}'.format(extban_prefix))

        ### Setting some mode level shit.
        ### +v = 1
        ### +h = 2
        ### +o = 3
        ### +a = 4
        ### +q = 5
        ### oper = 6
        ### server = 7
        modeLevel = {
            ### Channel statuses. Users with +h or higher can always remove their own status.
            'v': 2,
            'h': 3,
            'o': 3,
            'a': 4,
            'q': 5
        }
        for t in ircd.channel_modes:
            for m in ircd.channel_modes[t]:
                level = ircd.channel_modes[t][m][0]
                modeLevel[m] = level
        for m in [m for m in recv[1] if m in chmodes+'+-' or m in channel.modes]:
            param_mode = None
            if m in ircd.parammodes:
                if (action == '+') or (action == '-' and m not in list(ircd.channel_modes[2])+list(ircd.channel_modes[3])):
                #if (action == '+') or (action == '-' and m in list(ircd.channel_modes[0])+list(ircd.channel_modes[1])):
                    paramcount += 1
                    if len(recv[2:]) > paramcount:
                        param_mode = recv[2:][paramcount]
                        logging.info('Param for {}{}: {}'.format(action, m, param_mode))
                    elif m not in ircd.channel_modes[0]:
                        logging.warning('Received param mode {}{} without param'.format(action, m))
                        continue
            if m in '+-' and action != m:
                action = m
                #logging.debug('Action set: {}'.format(action))
                if action != prevaction:
                    if modebuf and modebuf[-1] in '-+':
                        modebuf = modebuf[1:]
                    modebuf.append(action)
                    #logging.debug('Modebuf now: {}'.format(modebuf))
                prevaction = action
                continue

            if not action:
                action = '+'
            if m in modeLevel and modeLevel[m] == 6 and (type(self).__name__ != 'Server' and 'o' not in self.modes):
                continue
            if m in modeLevel and modeLevel[m] == 7 and type(self).__name__ != 'Server':
                continue
            if m not in '+-' and action != prevaction and ( (m in chmodes or m in ircd.chstatus) or (action in '+-' and m in channel.modes) ):
                modebuf.append(action)
                prevaction = action
            if m not in ircd.chstatus and m not in '+-':
                if m in modeLevel and self.chlevel(channel) < modeLevel[m] and not self.ocheck('o', 'override'):
                    continue
                elif m in modeLevel and self.chlevel(channel) < modeLevel[m] and modeLevel[m] != 6:
                    oper_override = True


            if m not in ircd.core_chmodes:
                c = next((x for x in ircd.channel_mode_class if x.mode == m), None)
                if c:
                    if not c.check(channel, action, param_mode):
                        continue
                    c.modebuf = modebuf
                    c.parambuf = parambuf
                    if (action == '+' and c.set_mode(self, channel, param_mode)) or (action == '-' and c.remove_mode(self, channel, param_mode)):
                        pass
                else:
                    # Modules like extbans do not have a mode, so we will check for hooks manually.
                    for callable in [callable for callable in ircd.hooks if callable[0].lower() == 'pre_'+hook and m in callable[1]]:
                        try:
                            callable[2](self, ircd, channel, modebuf, parambuf, action, param_mode)
                        except Exception as ex:
                            logging.exception(ex)

            if action == '+' and (m in chmodes or type(self).__name__ == 'Server'):
                ###
                ### SETTING CHANNEL MODES
                ###
                if m == 'l' and len(recv) > 2:
                    if not param_mode.isdigit():
                        continue
                    if int(param_mode) <= 0:
                        continue
                    if m in ircd.chan_params[channel] and int(ircd.chan_params[channel][m]) == int(param_mode):
                        continue
                    else:
                        if m not in channel.modes:
                            channel.modes += m
                        modebuf.append(m)
                        parambuf.append(param_mode)

                elif m == 'k' and m not in ircd.chan_params[channel]:
                    if m not in channel.modes:
                        channel.modes += m
                    modebuf.append(m)
                    parambuf.append(param_mode)


                elif m == 'L':
                    param_mode = param_mode.split(',')[0]
                    if param_mode[0] not in ircd.chantypes:
                        continue
                    redirect = None if 'L' not in channel.modes else ircd.chan_params[channel]['L']
                    if redirect == param_mode or param_mode.lower() == channel.name.lower():
                        continue
                    chan_exists = [chan for chan in ircd.channels if chan.name.lower() == param_mode.lower()]
                    if not chan_exists:
                        self.sendraw(690, ':Target channel {} does not exist.'.format(param_mode))
                        continue
                    if self.chlevel(chan_exists[0]) < 3 and not self.ocheck('o', 'override'):
                        self.sendraw(690, ':You must be opped on target channel {} to set it as redirect.'.format(chan_exists[0].name))
                        continue
                    if 'L' in chan_exists[0].modes:
                        self.sendraw(690, ':Destination channel already has +L.')
                        continue
                    elif self.chlevel(channel) < modeLevel[m]:
                        oper_override = True
                    if m not in channel.modes:
                        channel.modes += m
                    modebuf.append(m)
                    parambuf.append(param_mode)


                elif m in 'beI':
                    if extban_prefix and param_mode.startswith(extban_prefix):
                        continue
                    mask = makeMask(ircd, param_mode)
                    if m == 'b':
                        data = channel.bans
                        s = 'ban'
                    elif m == 'e':
                        data = channel.excepts
                        s = 'excepts'
                    elif m == 'I':
                        data = channel.invex
                        s = 'invex'
                    if mask not in data:
                        if len(data) >= ircd.maxlist[m] and type(self).__name__ == 'User':
                            self.sendraw(478, '{} {} :Channel {} list is full'.format(channel.name, mask, s))
                            continue
                        try:
                            setter = self.fullmask()
                        except:
                            setter = self.hostname
                        modebuf.append(m)
                        parambuf.append(mask)
                        data[mask] = {}
                        data[mask]['setter'] = setter
                        data[mask]['ctime'] = int(time.time())
                        continue

                elif m in ircd.chstatus:
                    timed = False
                    # + status
                    temp_user = param_mode
                    try:
                        t = param_mode.split(':')
                        temp_user = t[0]
                        try:
                            channel.temp_status
                        except:
                            channel.temp_status = {}
                        if valid_expire(t[1]):
                            timed = valid_expire(t[1])
                    except:
                        pass

                    user = list(filter(lambda u: u.uid == temp_user or u.nickname.lower() == temp_user.lower(), channel.users))
                    if not user:
                        continue
                    else:
                        user = user[0]
                    if m in channel.usermodes[user]:
                        continue
                    if type(self).__name__ != 'Server':
                        if self.chlevel(channel) < modeLevel[m] and not self.ocheck('o', 'override'):
                            continue
                        elif self.chlevel(channel) < modeLevel[m]:
                            oper_override = True

                    channel.usermodes[user] += m
                    modebuf.append(m)
                    parambuf.append(user.nickname)
                    if timed:
                        channel.temp_status[user] = {}
                        channel.temp_status[user][m] = {}
                        channel.temp_status[user][m]['ctime'] = int(time.time()) + timed
                        channel.temp_status[user][m]['action'] = '-'

                if m not in channel.modes and (m in list(ircd.channel_modes[3])+list(ircd.channel_modes[2])):
                    ### If the mode is not handled by modules, do it here.
                    if not next((x for x in ircd.channel_mode_class if x.mode == m), None):
                        modebuf.append(m)
                        channel.modes += m
                        logging.debug('Non-modulair mode "{}" has been handled by m_mode'.format(m))

                    if m == 'O' and len(channel.users) > 2:
                        for user in [user for user in channel.users if 'o' not in user.modes]:
                            cmd = ('KICK', '{} {} :Opers only'.format(channel.name, user.nickname))
                            commandQueue.append(cmd)

            elif action == '-' and ((m in chmodes or m in channel.modes) or type(self).__name__ == 'Server'):
                ###
                ### REMOVING CHANNEL MODES
                ###
                if m in channel.modes:
                    if m == 'l':
                        #channel.limit = 0
                        if 'L' in channel.modes: # Also unset -L because we do not need it anymore.
                            channel.modes = channel.modes.replace('L', '')
                            modebuf.append('L')
                            parambuf.append(ircd.chan_params[channel]['L'])

                    elif m == 'k':
                        if param_mode != ircd.chan_params[channel]['k']:
                            continue
                        parambuf.append(ircd.chan_params[channel][m])

                    elif m  == 'L':
                        parambuf.append(ircd.chan_params[channel]['L'])
                        #channel.redirect = None

                    elif m == 'P':
                        if len(channel.users) == 0:
                            ircd.channels.remove(channel)

                        try:
                            with open(ircd.rootdir+'/db/chans.db') as f:
                                current_perm = f.read().split('\n')[0]
                                current_perm = json.loads(current_perm)
                                del current_perm[channel.name]
                            with open(ircd.rootdir+'/db/chans.db', 'w+') as f:
                                json.dump(current_perm, f)
                        except Exception as ex:
                            logging.debug(ex)

                    if m in channel.modes:
                        # Only remove mode if it's a core mode. ChannelMode class handles the rest.
                        if m in ircd.core_chmodes:
                            channel.modes = channel.modes.replace(m, '')
                            modebuf.append(m)

                elif m in 'beI':
                    mask = makeMask(ircd, param_mode)
                    if m == 'b':
                        data = channel.bans
                    elif m == 'e':
                        data = channel.excepts
                    elif m == 'I':
                        data = channel.invex
                    if mask in data:
                        del data[mask]
                        parambuf.append(mask)
                        modebuf.append(m)
                    elif param_mode in data:
                        del data[param_mode]
                        parambuf.append(param_mode)
                        modebuf.append(m)
                    #continue
                elif m in ircd.chstatus:
                    timed = False
                    # -qaohv
                    temp_user = param_mode
                    try:
                        t = param_mode.split(':')
                        temp_user = t[0]
                        try:
                            channel.temp_status
                        except:
                            channel.temp_status = {}
                        if valid_expire(t[1]):
                            timed = valid_expire(t[1])
                    except:
                        pass
                    user = list(filter(lambda u: temp_user and u.uid == temp_user or u.nickname.lower() == temp_user.lower(), channel.users))
                    if not user:
                        continue
                    else:
                        user = user[0]
                    if m not in channel.usermodes[user]:
                        continue
                    if 'S' in user.modes and user.server.hostname in ircd.conf['settings']['ulines'] and not self.ocheck('o', 'override'):
                        self.sendraw(974, '{} :{} is a protected service bot'.format(m, user.nickname))
                        continue
                    elif 'S' in user.modes:
                        oper_override = True
                    if type(self).__name__ != 'Server':
                        if self.chlevel(channel) < modeLevel[m] and not self.ocheck('o', 'override') and user != self:
                            continue
                        elif self.chlevel(channel) < modeLevel[m]:
                            oper_override = True

                    channel.usermodes[user] = channel.usermodes[user].replace(m, '')
                    modebuf.append(m)
                    parambuf.append(user.nickname)
                    if timed:
                        channel.temp_status[user] = {}
                        channel.temp_status[user][m] = {}
                        channel.temp_status[user][m]['ctime'] = int(time.time()) + timed
                        channel.temp_status[user][m]['action'] = '+'

            if m in ircd.core_chmodes:
                ### Finally, call modules for core modes.
                for callable in [callable for callable in ircd.hooks if callable[0].lower() == 'pre_'+hook and m in callable[1]]:
                    try:
                        callable[2](self, ircd, channel, modebuf, parambuf, action, param_mode)
                    except Exception as ex:
                        logging.exception(ex)
            continue

        if not re.sub('[+-]', '', ''.join(modebuf)):
            return

        while modebuf[-1] in '+-':
            modebuf = modebuf[:-1]

        if channel.name[0] == '&':
            sync = False


        modes = ''.join(modebuf)
        total_modes, total_params = [], []
        if len(modebuf) > 1:
            mode_limit = modes.replace('+', '').replace('-', '')
            total_modes, total_params = [], []
            paramcount = 0
            action = ''
            for m in modes:
                if m in '+-':
                    action = m
                    total_modes.append(m)
                    continue

                total_modes.append(m)
                if m in list(ircd.channel_modes[1])+list(ircd.channel_modes[2]):
                    # If a module handles a channel mode with a param, but for some reason forgets to add it to the chan_params dict,
                    # we will add it here. It is really important that param-modes have their params saved.
                    if action == '+':
                        if m in ircd.core_chmodes:
                            logging.debug('[core] Storing param of {}: {}'.format(m, parambuf[paramcount]))
                            ircd.chan_params[channel][m] = parambuf[paramcount]
                        elif m not in ircd.chan_params[channel]:
                            logging.debug('[fallback] Storing param of {}: {}'.format(m, parambuf[paramcount]))
                            ircd.chan_params[channel][m] = parambuf[paramcount]

                    elif action == '-' and m in ircd.chan_params[channel]:
                        logging.debug('[fallback] Forgetting param of {}: {}'.format(m, ircd.chan_params[channel][m]))
                        del ircd.chan_params[channel][m]

                for callable in [callable for callable in ircd.hooks if callable[0].lower() == hook]:
                    try:
                        callable[2](self, ircd, channel, modes, parambuf)
                    except Exception as ex:
                        logging.exception(ex)

                if m in ircd.parammodes and (m not in ircd.channel_modes[2] or action == '+'):
                    total_params.append(parambuf[paramcount])
                    paramcount += 1
                totalLength = len(''.join(total_modes)+' '+' '.join(total_params))
                mode_amount = len(re.sub('[+-]', '', ''.join(total_modes)))
                if mode_amount >= MAXMODES or totalLength >= 400:
                    all_modes = ''.join(total_modes)+' '+' '.join(total_params)
                    if oper_override and type(self).__name__ != 'Server':
                        sourceServer.snotice('s', '*** OperOverride by {} ({}@{}) with MODE {} {}'.format(sourceUser.nickname, sourceUser.ident, sourceUser.hostname, channel.name, all_modes))
                    if sync:
                        ircd.new_sync(ircd, sourceServer, ':{} MODE {} :{}'.format(displaySource, channel.name, all_modes if type(self).__name__ == 'User' else rawModes))
                    sourceUser.broadcast(channel.users, 'MODE {} {}'.format(channel.name, all_modes), source=sourceUser)
                    total_modes, total_params = [action], []
                    continue
            if len(total_modes) > 1:
                all_modes = ''.join(total_modes)+' '+' '.join(total_params)
                if oper_override and type(self).__name__ != 'Server':
                    sourceServer.snotice('s', '*** OperOverride by {} ({}@{}) with MODE {} {}'.format(sourceUser.nickname, sourceUser.ident, sourceUser.hostname, channel.name, all_modes))
                if sync:
                    ircd.new_sync(ircd, sourceServer, ':{} MODE {} :{}'.format(displaySource, channel.name, all_modes if type(self).__name__ == 'User' else rawModes))
                sourceUser.broadcast(channel.users, 'MODE {} {}'.format(channel.name, all_modes), source=sourceUser)

            for cmd, data in commandQueue:
                ircd.handle(cmd, data)

            save_db(ircd)
            modebuf = []
            parambuf = []

    except Exception as ex:
        logging.exception(ex)




@ircd.Modules.command
class Mode(ircd.Command):
    """
    Change channel or user modes.
    For an overview of available modes, type /HELPOP CHMODES or /HELPOP UMODES
    -
    Syntax:  MODE <channel/user> <modes> [params]
    Example: MODE #Home +m
             MODE Alice +c
    """
    def __init__(self):
        self.command = 'mode'
        self.params = 1
        self.support = [('MAXLIST',), ('PREFIX',), ('MODES', str(MAXMODES),), ('CHANMODES',)]
        self.server_support = 1


    def execute(self, client, recv, override=True):
        global oper_override
        oper_override = False
        regex = re.compile("\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)
        recv = regex.sub('', ' '.join(recv)).split()
        try:
            if type(client).__name__ == 'Server':
                sourceServer = client
                S = recv[0][1:]
                sourceUser = [s for s in self.ircd.servers+[self.ircd] if s.sid == S or s.hostname == S]+[u for u in self.ircd.users if u.uid == S or u.nickname == S]
                if sourceUser:
                    sourceUser = sourceUser[0]
                else:
                    sourceUser = client
                target = recv[2]
                if target[0] in self.ircd.chantypes:
                    channel = list(filter(lambda c: c.name.lower() == recv[2].lower(), self.ircd.channels))
                    if not channel:
                        return
                    processModes(client, self.ircd, channel[0], recv[2:], sourceServer=sourceServer, sourceUser=sourceUser)
                    return
                recv = recv[1:]
            else:
                sourceServer = client.server
                sourceUser = client

            if len(recv) == 2 and recv[1][:1] in self.ircd.chantypes:
                try:
                    if recv[1][0] == '+':
                        return
                    channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), self.ircd.channels))
                    if not channel:
                        return client.sendraw(401, '{} :No such channel'.format(recv[1]))
                    channel = channel[0]
                    if 's' in channel.modes and client not in channel.users and not client.ocheck('o', 'override'):
                        return
                    params = []
                    show_params = []
                    for m in channel.modes:
                        if channel in self.ircd.chan_params and m in self.ircd.chan_params[channel]:
                            show_params.append(self.ircd.chan_params[channel][m])
                    #client.sendraw(324, '{} +{} {}'.format(channel.name, channel.modes, ' '.join(params) if params and (client in channel.users or 'o' in client.modes) else ''))
                    client.sendraw(324, '{} +{} {}'.format(channel.name, channel.modes, ' '.join(show_params) if show_params and (client in channel.users or 'o' in client.modes) else ''))
                    client.sendraw(329, '{} {}'.format(channel.name, channel.creation))
                except Exception as ex:
                    logging.exception(ex)
                return

            elif recv[1][0] not in self.ircd.chantypes:
                user = list(filter(lambda u: u.nickname.lower() == recv[1].lower() or u.uid == recv[1], self.ircd.users))
                if not user:
                    return

                if user[0] != client and sourceServer == self.ircd and not self.ircd.ocheck('o', 'remotemode') and type(client).__name__ != 'Server':
                    return
                chgumode(client, self.ircd, recv, override, sourceServer=sourceServer, sourceUser=sourceUser)
                return

            ######################
            ### CHANNEL MODES ####
            ######################
            channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), self.ircd.channels))
            if not channel:
                return client.sendraw(401, '{} :No such channel'.format(recv[1]))

            channel = channel[0]

            for v in [v for v in channel.bans if not v]:
                del channel.bans[b]
            for v in [v for v in channel.excepts if not v]:
                del channel.excepts[b]
            for v in [v for v in channel.invex if not v]:
                del channel.invex[b]

            if type(client).__name__ == 'Server' and not client.eos and client != self.ircd:
                return

            if type(client).__name__ != 'Server':
                if client not in channel.users and not client.ocheck('o', 'override'):
                    return client.sendraw(401, '{} :No such channel'.format(recv[1]))

            if len(recv) == 3:
                if recv[2] in ['+b', 'b']:
                    for entry in OrderedDict(reversed(list(channel.bans.items()))):
                        client.flood_safe = True
                        client.sendraw(367, '{} {} {} {}'.format(channel.name, entry, channel.bans[entry]['setter'], channel.bans[entry]['ctime']))
                    return client.sendraw(368, '{} :End of Channel Ban List'.format(channel.name))
                elif recv[2] in ['+e', 'e']:
                    if client.chlevel(channel) < 3 and not client.ocheck('o', 'override'):
                        return client.sendraw(482, '{} :You are not allowed to view the excepts list'.format(channel.name))
                    for entry in OrderedDict(reversed(list(channel.excepts.items()))):
                        client.flood_safe = True
                        client.sendraw(348, '{} {} {} {}'.format(channel.name, entry, channel.excepts[entry]['setter'], channel.excepts[entry]['ctime']))
                    return client.sendraw(349, '{} :End of Channel Exceptions List'.format(channel.name))
                elif recv[2] in ['+I', 'I']:
                    if client.chlevel(channel) < 3 and not client.ocheck('o', 'override'):
                        return client.sendraw(482, '{} :You are not allowed to view the invex list'.format(channel.name))
                    for entry in OrderedDict(reversed(list(channel.invex.items()))):
                        client.flood_safe = True
                        client.sendraw(346, '{} {} {} {}'.format(channel.name, entry, channel.invex[entry]['setter'], channel.invex[entry]['ctime']))
                    return client.sendraw(347, '{} :End of Channel Invite List'.format(channel.name))

            if type(client).__name__ != 'Server':
                if client.chlevel(channel) < 2 and not client.ocheck('o', 'override'):
                       return client.sendraw(482, '{} :You\'re not a channel operator'.format(channel.name))
                elif client.chlevel(channel) < 2:
                    oper_override = True
            processModes(client, self.ircd, channel, recv[1:], sourceServer=sourceServer, sourceUser=sourceUser)

        except Exception as ex:
            logging.exception(ex)


def chgumode(client, ircd, recv, override, sourceServer=None, sourceUser=None):
    try:
        modebuf = []
        action = ''
        target = list(filter(lambda u: u.nickname.lower() == recv[1].lower(), ircd.users))
        if not target:
            return

        target = target[0]

        if type(client).__name__ == 'Server':
            override = True
            displaySource = client.hostname
            if client != ircd:
                displaySource = sourceUser.nickname
        else:
            if client.server != ircd:
                override = True
            displaySource = client.nickname
        client = sourceUser
        warn = []
        unknown = []
        showsno = False
        for m in str(recv[2]):
            if 'modelock' in ircd.conf['settings'] and m in ircd.conf['settings']['modelock'] and not client.ocheck('o', 'override') and not override:
                if 'lock' not in warn:
                    warn.append('lock')
                    ircd.broadcast([client], 'NOTICE {} :The following modes cannot be changed: \'{}\''.format(client.nickname, ircd.conf['settings']['modelock']))
                    warn = []
                continue


            if m == 'r' and type(client).__name__ != 'Server':
                if client.server.hostname not in ircd.conf['settings']['ulines']:
                    continue
            if m in '+-' and action != m:
                action = m
                try:
                    if modebuf[-1] in '+-':
                        del modebuf[-1]
                except:
                    pass
                modebuf.append(action)
            else:

                for umode in [umode for umode in ircd.user_mode_class if umode.mode == m]:
                    #logging.debug('/MODE: Found a UserMode class: {}'.format(umode))
                    umode.modebuf = modebuf
                    if (action == '+' and umode.give_mode(client)) or (action == '-' and umode.take_mode(client)):
                            #modebuf.append(m)
                            continue

                if m not in '+-' and m not in ircd.user_modes and type(client).__name__ != 'Server':
                    if m not in unknown and not override:
                        unknown.append(m)
                    continue
                if m in 'z' and not override:
                    if m not in warn:
                        client.sendraw(ircd.ERR.UMODEUNKNOWNFLAG, 'Mode +{} may only be set by servers'.format(m))
                        warn.append(m)
                    continue
                    warn = []
                if m in 'ohsqHW' and (not client.operaccount or m not in ircd.conf['opers'][client.operaccount]['modes']) and not override:
                    continue
                if action == '+':
                    if m == 'x':
                        cloaked = cloak(ircd, client.hostname)
                        client.setinfo(cloaked, t='host', source=sourceServer)
                        client.cloakhost = cloaked
                    elif m == 'S' and client.server.hostname not in ircd.conf['settings']['ulines']:
                        client.sendraw(ircd.ERR.UMODEUNKNOWNFLAG, 'Mode +{} may only be set by servers'.format(m))
                        continue
                    elif m == 's':
                        if len(recv) > 3:
                            for s in recv[3]:
                                if s in '+-':
                                    saction = s
                                    continue
                                if saction == '-' and s in target.snomasks:
                                    showsno = True
                                    target.snomasks = target.snomasks.replace(s, '')
                                    continue
                                if saction == '+' and s in ircd.snomasks and (client.operaccount and s in ircd.conf['opers'][client.operaccount]['snomasks']) and s not in target.snomasks:
                                    showsno = True
                                    target.snomasks += s
                                    continue

                    elif m == 'o':
                        updated = []
                        for user in ircd.users:
                            for user in [user for user in ircd.users if 'operwatch' in user.caplist and user not in updated and user.socket]:
                                common_chan = list(filter(lambda c: user in c.users and client in c.users, ircd.channels))
                                if not common_chan:
                                    continue
                                user._send(':{} UMODE {}{}'.format(client.fullmask(), action, m))
                                updated.append(user)

                    # Handle core modes. These aren't handled by UserMode class.
                    if m not in target.modes:
                        if m in 'sqHSW' and (not hasattr(target, 'opermodes') or m not in target.opermodes):
                            if not hasattr(target, 'opermodes'):
                                target.opermodes = ''
                            target.opermodes += m
                        target.modes += m
                        modebuf.append(m)


                if action == '-' and m in target.modes:
                    if m == 'x':
                        client.setinfo(client.hostname, t='host', source=sourceServer)
                    elif m == 'S' and client.server.hostname not in ircd.conf['settings']['ulines']:
                        client.sendraw(ircd.ERR.UMODEUNKNOWNFLAG, 'Mode +{} may only be set by servers'.format(m))
                        continue
                    elif m == 'r':
                        target.svid = '*'
                    elif m == 's':
                        target.snomasks = ''
                    elif m == 'o':
                        target.operflags = []
                        ### Assign a class.
                        for cls in ircd.conf['allow']:
                            clientmaskhost = '{}@{}'.format(target.ident, target.ip)
                            if 'ip' in ircd.conf['allow'][cls]:
                                clientmask = '{}@{}'.format(target.ident, target.ip)
                                isMatch = match(ircd.conf['allow'][cls]['ip'], clientmask)
                            if 'hostname' in ircd.conf['allow'][cls]:
                                clientmask = '{}@{}'.format(target.ident, target.hostname)
                                isMatch = match(ircd.conf['allow'][cls]['hostname'], clientmask)
                            if isMatch:
                                if 'options' in ircd.conf['allow'][cls]:
                                    if 'ssl' in ircd.conf['allow'][cls]['options'] and not target.ssl:
                                        continue
                                target.cls = cls

                        if hasattr(target, 'opermodes'):
                            for mode in [m for m in target.opermodes if m in target.modes]:
                                modes.append(mode)
                                if mode == 's':
                                    target.snomasks = ''
                        if target.swhois:
                            operSwhois = ''
                            if 'swhois' in ircd.conf['opers'][target.operaccount]:
                                operSwhois = ircd.conf['opers'][target.operaccount]['swhois']
                            if operSwhois in target.swhois:
                                target.swhois.remove(operSwhois)
                            if target.operswhois in target.swhois:
                                target.swhois.remove(target.operswhois)
                            data = ':{} SWHOIS {} :'.format(ircd.sid, target.uid)
                            ircd.new_sync(ircd, sourceServer, data)
                            for line in target.swhois:
                                data = ':{} SWHOIS {} :{}'.format(ircd.sid, target.uid, line)
                                ircd.new_sync(ircd, sourceServer, data)

                        target.opermodes = ''
                        client.operaccount = None

                        updated = []
                        for user in ircd.users:
                            for user in [user for user in ircd.users if 'operwatch' in user.caplist and user not in updated and user.socket]:
                                common_chan = list(filter(lambda c: user in c.users and client in c.users, ircd.channels))
                                if not common_chan:
                                    continue
                                user._send(':{} UMODE {}{}'.format(client.fullmask(), action, m))
                                updated.append(user)

                    # Handle core modes. These aren't handled by UserMode class.
                    if m not in modebuf:
                        modebuf.append(m)
                    # Removing modes from user class.
                    for mode in modebuf:
                        target.modes = target.modes.replace(mode, '')

        if 'o' in target.modes:
            target.modes = 'o'+target.modes.replace('o', '')
        if len(modebuf) > 1 and ' '.join(modebuf)[-1] in '+-':
            del modebuf[-1]
        modes = ''.join(modebuf)
        if len(modes) > 1:
            target._send(':{} MODE {} :{}'.format(displaySource, target.nickname, modes))
            if client != target:
                client.sendraw(ircd.ERR.UMODEUNKNOWNFLAG, 'UMODE {} :{}'.format(target.nickname, modes))

            if target.server != ircd:
                ircd.new_sync(ircd, sourceServer, ':{} MODE {} {}'.format(displaySource, target.nickname, modes))
            else:
                ircd.new_sync(ircd, sourceServer, ':{} UMODE2 {}'.format(target.uid, modes))

        if 's' in modes or showsno:
            ircd.new_sync(ircd, sourceServer, ':{} BV +{}'.format(target.uid, target.snomasks))
            target.sendraw(8, 'Server notice mask (+{})'.format(target.snomasks))

        if unknown:
            client.sendraw(ircd.ERR.UMODEUNKNOWNFLAG, 'Mode{} \'{}\' not found'.format('s' if len(unknown) > 1 else '', ''.join(unknown)))

    except Exception as ex:
        logging.exception(ex)
