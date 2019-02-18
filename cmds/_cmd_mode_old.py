import os
import importlib
import sys
import time

from handle.functions import _print, valid_expire, match

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

def makeMask(localServer, data):
    nick, ident, host = '', '', ''
    nick = data.split('!')[0]
    if nick == '' or '@' in nick or ('.' in nick and '@' not in data):
        nick = '*'
    if len(nick) > localServer.nicklen:
        nick = '*{}'.format(nick[-20:])
    try:
        if '@' in data:
            ident = data.split('@')[0]
            if '!' in ident:ident = data.split('@')[0].split('!')[1]
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

def extBans(self, localServer, recv, channel, paramcount, m, commandQueue):
    rawParam = recv[2:][paramcount]
    if m == 'b':
        if rawParam[:2] == '~T':
            ### Text block.
            if rawParam.split(':')[1] not in ['block', 'replace'] or len(rawParam.split(':')) < 3:
                return False
            bAction = rawParam.split(':')[1]
            if not rawParam.split(':')[2:]:
                return False
            if bAction == 'replace':
                ### Replace requires an additional parameter: ~T:replace:match:replacement
                if len(rawParam.split(':')) < 4:
                    return False
                if not rawParam.split(':')[3]:
                    return False
            return rawParam

        elif rawParam[:2] == '~C':
            ### Channel block.
            if len(rawParam.split(':')) < 2:
                return False
            chanBan = rawParam.split(':')[1]
            if chanBan[0] != '#':
                return False
            tempchan = list(filter(lambda c: c.name.lower() == chanBan.lower(), localServer.channels))
            if tempchan and len(channel.users) > 2:
                tempchan = tempchan[0]
                ### tempchan users are forbidden on channel.
                for user in [user for user in channel.users if tempchan in user.channels and user.chlevel(channel) < 3 and not user.ocheck('o', 'override')]:
                    cmd = ('KICK', '{} {} :Users from {} are not welcome here'.format(channel.name, user.nickname, tempchan.name))
                    commandQueue.append(cmd)
            return rawParam

        elif rawParam[:2] == '~t':
            ### Channel block.
            if len(rawParam.split(':')) < 3:
                return False
            bTime = rawParam.split(':')[1]
            if not bTime.isdigit():
                return False
            banmask = makeMask(localServer,rawParam.split(':')[2])
            return '{}:{}'.format(':'.join(rawParam.split(':')[:2]), banmask)

def chmodeF(self, localServer, recv, channel, paramcount, action):
    try:
        ### Format: +f [amount:type:secs][action:duration] --- duration is in minutes.

        ### Example: +f 3:j:10 (3 join in 10 sec, default is +i for 1 minute)
        ### Example: +f 3:j:10:i:2 (3 joins in 10 sec, sets channel to +i for 2 minutes)
        ### Example: +f 3:j:10:R:5 (3 joins in 10 sec, sets channel to +R for 5 minutes)

        ### Example: +f 3:m:10 (3 messages in 10 sec, default action is kick)
        ### Example: +f 5:m:3:b:1 (5 messages in 3 sec, will ban/kick for 1 minute)

        ### Setting vars
        floodTypes = 'jm'
        #print('Function called: chmodeF with paramcount: {}'.format(paramcount))
        #print('Recv: {}'.format(recv))
        try:
            p = recv[2:][paramcount]
        except:
            return False
        #print('Params received: {}'.format(p))

        if action == '+':
            if len(p) < 2:
                #print('Param too short')
                return False
            #print('Requesting to set flood protection, checking params')
            if p[0] == '-':
                type = p[1]
                #print('Removing flood type')
                if type not in floodTypes or type not in channel.chmodef:
                    #print('Type {} not found in {}'.format(type,channel.chmodef))
                    return False
                del channel.chmodef[type]
                #print('Success! Returning {}'.format(type))
                return '-{}'.format(type)

            if len(p.split(':')) < 3:
                #print('Invalid param format')
                return False
            if not p.split(':')[0].isdigit():
                #print('Amount must be a number')
                return False
            if p.split(':')[1] not in floodTypes:
                #print('Invalid flood type')
                return False
            if not p.split(':')[2].isdigit():
                #print('Seconds must be a number (really!)')
                return False
            ### All is good, set the mode.
            amount = int(p.split(':')[0])
            type = p.split(':')[1]
            secs = int(p.split(':')[2])
            if type in channel.chmodef:
                #print('Updating current protection')
                del channel.chmodef[type]

            ### Check for alternative action:
            action = None
            try:
                action = p.split(':')[3]
            except:
                pass
            if action:
                ### We have an action, check if it is valid.
                #print('Checking alternative action')
                if type == 'm' and action not in ['m','b']:
                    ### Invalid action, reverting to default.
                    action = None
                elif type == 'j' and action not in ['i','R']:
                    ### Invalid action, reverting to default.
                    action = None
                if action:
                    ### Ok, valid action.
                    try:
                        duration = p.split(':')[4]
                        if not duration.isdigit():
                            #print('Invalid duration, unsetting action')
                            action = None
                        else:
                            duration = int(duration)
                            #print('Duration for {} set to: {}'.format(action,duration))
                    except:
                        #print('Alternative action was given, but no duration. Unsetting action')
                        action = None

            channel.chmodef[type] = {}
            channel.chmodef[type]['amount'] = amount
            channel.chmodef[type]['time']   = secs
            if not action:
                p = ':'.join(p.split(':')[:3])
                ### Default action
                if type == 'm':
                    channel.chmodef[type]['action'] = 'kick'
                elif type == 'j':
                    channel.chmodef[type]['action'] = 'i'
                    channel.chmodef[type]['actionSet'] = None
                    channel.chmodef[type]['duration'] = 1

            else:
                channel.chmodef[type]['action'] = str(action)
                channel.chmodef[type]['duration'] = duration
                channel.chmodef[type]['actionSet'] = None

            #print('Success! Returning {}'.format(p))
            return p

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e)

oper_override = False
def processModes(self, localServer, channel, recv, sync=True, source=None):
    try:
        #print('processModes self: {}'.format(self))
        #print('processModes source.hostname: {}'.format(source.hostname))
        ### Source will be a class. Yes, it will. So act accordingly!
        rawModes = ' '.join(recv[1:])
        if type(source).__name__ == 'User':
            ### Change source to its server.
            displaySource   = source.uid
            sourceServer = source.server
        else:
            displaySource   = source.sid
            sourceServer = source
            if not source.eos and source != localServer:
                sync = False
        ### displaySource will be used to pass along to syncToServers()
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e)
    try:
        chstatus = localServer.chstatus
        chmodes = ''.join(localServer.allchmodes.split(',')[0:])+chstatus
        ### Modes that require a parameter.
        paramModes = localServer.chstatus+''.join(localServer.allchmodes.split(',')[0])
        global tmodes, action, prevaction
        action = ''
        prevaction = ''
        commandQueue = []
        tmodes = []
        param = []
        paramcount = 0
        keyset, limitset, redirectset = False, False, False
        global oper_override
        ### Setting some mode level shit.
        ### +v = 1
        ### +h = 2
        ### +o = 3
        ### +a = 4
        ### +q = 5
        modeLevel = {
            ### Channel statuses. Users with +h or higher can always remove their own status.
            'v': 2,
            'h': 3,
            'o': 3,
            'a': 4,
            'q': 5,

            ### Non-paramental channel modes.
            's': 3,
            'z': 3,
            'N': 4,
            'Q': 4,
            'V': 3
        }
        char_pos = 0
        for m in recv[1]:
            char_pos += 1
            if m == 'r' and type(self).__name__ != 'Server':
                continue
            temp_tmodes = ''.join(tmodes)
            temp_param = ' '.join(param)
            totalLength = len(temp_tmodes+' '+temp_param)
            #print('totalLength: {}'.format(totalLength))
            if len(tmodes) > localServer.maxmodes or totalLength >= 400:
                tmodes = ''.join(tmodes)
                param = ' '.join(param)
                modes = tmodes+' '+param
                self.broadcast(channel.users, 'MODE {} {}'.format(channel.name, modes), source=source)
                if sync:
                    localServer.syncToServers(localServer, source, ':{} MODE {} {}'.format(displaySource, channel.name, modes if type(self).__name__ == 'User' else rawModes))

                tmodes, param = [prevaction], []

            if m in '+-' and action != m:
                try:
                    if ''.join(tmodes[-1]) in '+-':
                        del tmodes[-1]
                except:
                    pass
                action = m
                continue
            if not action:
                action = '+'
            for c in m:
                if m not in '+-' and action != prevaction and (m in chmodes or m in chstatus):
                    tmodes.append(action)
                    prevaction = action
            else:

                ### Still need to work on this. If no modeLevel is set, the default of minimum +h is used.
                ### Excluding chstatus in this check because users can still remove their OWN status.
                if m in chmodes and m not in chstatus and m in modeLevel:
                    if self.chlevel(channel) < modeLevel[m] and not self.ocheck('o', 'override'):
                        if m in paramModes:
                           paramcount += 1
                        continue
                    elif self.chlevel(channel) < modeLevel[m]:
                        oper_override = True

                if action == '+' and (m in chmodes or type(self).__name__ == 'Server'):
                    ###
                    ### SETTING CHANNEL MODES
                    ###
                    if m == 'l' and len(recv) > 2 and not limitset:
                        try:
                            p = recv[2:][paramcount]
                        except Exception as ex:
                            continue
                        if not p.isdigit():
                            continue
                        if int(p) <= 0:
                            continue
                        if channel.limit == int(p):
                            continue
                        else:
                            limitset = True
                            if m not in channel.modes:
                                channel.modes += m
                            tmodes.append(m)
                            param.append(p)
                            paramcount += 1
                            channel.limit = int(p)
                            continue

                    elif m == 'k' and not keyset:
                        try:
                            p = recv[2:][paramcount]
                        except Exception as ex:
                            continue
                        if channel.key == p:
                            continue
                        keyset = True
                        if m not in channel.modes:
                            channel.modes += m
                        tmodes.append(m)
                        param.append(p)
                        paramcount += 1
                        channel.key = p
                        continue

                    elif m == 'L':
                        if 'l' not in channel.modes:
                            paramcount += 1
                            continue
                        if not redirectset:
                            try:
                                p = recv[2:][paramcount]
                            except Exception as ex:
                                continue
                            if p[0] != '#':
                                continue
                            if channel.redirect == p or p.lower() == channel.name.lower():
                                continue
                            redirectset = True
                            if m not in channel.modes:
                                channel.modes += m
                            tmodes.append(m)
                            param.append(p)
                            paramcount += 1
                            channel.redirect = p
                            continue

                    elif m == 'f':
                        p = chmodeF(self, localServer, recv, channel, paramcount, action)
                        if p:
                            tmodes.append(m)
                            param.append(p)
                            if m not in channel.modes:
                                channel.modes += m
                            paramcount += 1
                        continue

                    elif m == 'O':
                        if type(self).__name__ != 'Server' and 'o' not in self.modes:
                            continue
                    elif m in 'beI':
                        try:
                            rawParam = recv[2:][paramcount]
                        except:
                            paramcount += 1
                            continue
                        if rawParam.startswith('~'):
                            #global commandQueue
                            mask = extBans(self, localServer, recv, channel, paramcount, m, commandQueue)
                            if not mask:
                                paramcount += 1
                                continue
                        else:
                            mask = makeMask(localServer, rawParam)
                        if m == 'b':
                            if mask not in channel.bans:
                                if len(channel.bans) >= localServer.maxlist[m] and type(self).__name__ == 'User':
                                    self.sendraw(478, '{} {} :Channel ban list is full'.format(channel.name, mask))
                                    paramcount += 1
                                    continue
                                try:
                                    setter = self.fullmask()
                                except:
                                    setter = self.hostname
                                paramcount += 1
                                tmodes.append(m)
                                param.append(mask)
                                channel.bans[mask] = {}
                                channel.bans[mask]['setter'] = setter
                                channel.bans[mask]['ctime'] = int(time.time())
                                continue
                            paramcount += 1
                            continue
                        if m == 'e':
                            if mask not in channel.excepts:
                                if len(channel.excepts) >= localServer.maxlist[m] and type(self).__name__ == 'User':
                                    self.sendraw(478, '{} {} :Channel excepts list is full'.format(channel.name, mask))
                                    paramcount += 1
                                    continue
                                try:
                                    setter = self.fullmask()
                                except:
                                    setter = self.hostname
                                paramcount += 1
                                tmodes.append(m)
                                param.append(mask)
                                channel.excepts[mask] = {}
                                channel.excepts[mask]['setter'] = setter
                                channel.excepts[mask]['ctime'] = int(time.time())
                                continue
                            paramcount += 1
                            continue
                        if m == 'I':
                            if mask not in channel.invex:
                                if len(channel.invex) >= localServer.maxlist[m] and type(self).__name__ == 'User':
                                    self.sendraw(478, '{} {} :Channel invex list is full'.format(channel.name, mask))
                                    paramcount += 1
                                    continue
                                try:
                                    setter = self.fullmask()
                                except:
                                    setter = self.hostname
                                paramcount += 1
                                tmodes.append(m)
                                param.append(mask)
                                channel.invex[mask] = {}
                                channel.invex[mask]['setter'] = setter
                                channel.invex[mask]['ctime'] = int(time.time())
                                continue
                            paramcount += 1
                            continue

                    elif m in chstatus:
                        timed = False
                        # + status
                        try:
                            temp_user = recv[2:][paramcount]
                        except:
                            paramcount += 1
                            continue
                        ### Check to see for timed shit.
                        try:
                            t = recv[2:][paramcount].split(':')
                            temp_user = t[0]
                            ### This is only temporary.
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
                            paramcount += 1
                            continue
                        else:
                            user = user[0]
                        if m in channel.usermodes[user] or '^' in user.modes:
                            paramcount += 1
                            continue
                        if type(self).__name__ != 'Server':
                            if self.chlevel(channel) < modeLevel[m] and not self.ocheck('o', 'override'):
                                paramcount += 1
                                continue
                            elif self.chlevel(channel) < modeLevel[m]:
                                oper_override = True
                        try:
                            if m == 'o' and channel.name.lower() == localServer.conf['settings']['helpchan'].lower() and 'h' not in user.modes:
                                user.modes += 'h'
                                localServer.syncToServers(localServer, source, ':{} UMODE2 +h'.format(self.uid))
                        except:
                            pass
                        channel.usermodes[user] += m
                        tmodes.append(m)
                        param.append(user.nickname)
                        paramcount += 1
                        if timed:
                            channel.temp_status[user] = {}
                            channel.temp_status[user][m] = {}
                            channel.temp_status[user][m]['ctime'] = int(time.time()) + timed
                            channel.temp_status[user][m]['action'] = '-'
                        continue
                    # Rest of the modes.

                    if m not in channel.modes:
                        tmodes.append(m)
                        channel.modes += m
                        if m == 'O' and len(channel.users) > 2:
                            for user in [user for user in channel.users if 'o' not in user.modes]:
                                cmd = ('KICK', '{} {} :Opers only'.format(channel.name, user.nickname))
                                commandQueue.append(cmd)
                        continue

                elif action == '-' and (m in chmodes or type(self).__name__ == 'Server'):
                    ###
                    ### REMOVING CHANNEL MODES
                    ###
                    if m in channel.modes:
                        if m == 'l':
                            channel.limit = 0
                            if 'L' in channel.modes:
                                channel.modes = channel.modes.replace('L', '')
                                tmodes.append('L')
                                #print('Channel redirect: {}'.format(channel.redirect))
                                param.append(channel.redirect)
                                channel.redirect = None

                        elif m == 'k':
                            try:
                                p = recv[2:][paramcount]
                            except Exception as ex:
                                continue
                            if p != channel.key:
                                continue
                            param.append(channel.key)
                            channel.key = None
                            paramcount += 1

                        elif m  == 'L':
                            channel.redirect = None

                        elif m == 'f':
                            channel.chmodef = {}

                        channel.modes = channel.modes.replace(m, '')
                        tmodes.append(m)
                    elif m in 'beI':
                        try:
                            # Checking both mask forms. Only for removing.
                            rawmask = recv[2:][paramcount]
                            mask = makeMask(localServer, recv[2:][paramcount])
                        except:
                            continue
                        if m == 'b':
                            if mask in channel.bans:
                                param.append(mask)
                                paramcount += 1
                                del channel.bans[mask]
                                tmodes.append(m)
                                continue
                            elif rawmask in channel.bans:
                                param.append(rawmask)
                                paramcount += 1
                                del channel.bans[rawmask]
                                tmodes.append(m)
                                continue
                            paramcount += 1
                            continue
                        if m == 'e':
                            if mask in channel.excepts:
                                param.append(mask)
                                paramcount += 1
                                del channel.excepts[mask]
                                tmodes.append(m)
                                continue
                            elif rawmask in channel.excepts:
                                param.append(rawmask)
                                paramcount += 1
                                del channel.excepts[rawmask]
                                tmodes.append(m)
                                continue
                            paramcount += 1
                            continue
                        if m == 'I':
                            if mask in channel.invex:
                                param.append(mask)
                                paramcount += 1
                                del channel.invex[mask]
                                tmodes.append(m)
                                continue
                            elif rawmask in channel.invex:
                                param.append(rawmask)
                                paramcount += 1
                                del channel.invex[rawmask]
                                tmodes.append(m)
                                continue
                            paramcount += 1
                            continue

                    elif m in chstatus:
                        timed = False
                        # -qaohv
                        try:
                            temp_user = recv[2:][paramcount]
                        except:
                            paramcount += 1
                            continue
                        ### Check to see for timed shit.
                        try:
                            t = recv[2:][paramcount].split(':')
                            temp_user = t[0]
                            ### This is only temporary.
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
                            paramcount += 1
                            continue
                        else:
                            user = user[0]
                        if m not in channel.usermodes[user] or '^' in user.modes:
                            paramcount += 1
                            continue
                        if 'S' in set(user.modes) and not self.ocheck('o', 'override'):
                            self.sendraw(974, '{} :{} is a protected service bot'.format(m, user.nickname))
                            paramcount += 1
                            continue
                        if type(self).__name__ != 'Server':
                            if self.chlevel(channel) < modeLevel[m] and not self.ocheck('o', 'override') and user != self:
                                paramcount += 1
                                continue
                            elif self.chlevel(channel) < modeLevel[m]:
                                oper_override = True

                        try:
                            if m == 'o' and channel.name.lower() == localServer.conf['settings']['helpchan'].lower() and 'h' in user.modes and 'o' not in user.modes:
                                user.modes = user.modes.replace('h', '')
                                localServer.syncToServers(localServer, self, ':{} UMODE2 -h'.format(self.uid))
                        except:
                            pass
                        channel.usermodes[user] = channel.usermodes[user].replace(m, '')
                        paramcount += 1
                        tmodes.append(m)
                        param.append(user.nickname)
                        if timed:
                            channel.temp_status[user] = {}
                            channel.temp_status[user][m] = {}
                            channel.temp_status[user][m]['ctime'] = int(time.time()) + timed
                            channel.temp_status[user][m]['action'] = '+'
                        continue

        if len(tmodes) == 0:
            return
        if ''.join(tmodes[-1]) in '+-':
            del tmodes[-1]
        tmodes = ''.join(tmodes)
        param = ' '.join(param)
        modes = tmodes+' '+param
        if len(tmodes) > 1:
            ### Send oper override notice?
            try:
                if oper_override:
                    localServer.snotice('s', '*** OperOverride by {} ({}@{}) with MODE {} {}'.format(self.nickname, self.ident, self.hostname, channel.name, modes))
            except Exception as ex:
                print(ex)
            if sync:
                localServer.syncToServers(localServer, source, ':{} MODE {} {}'.format(displaySource, channel.name, modes if type(self).__name__ == 'User' else rawModes))
            self.broadcast(channel.users, 'MODE {} {}'.format(channel.name, modes), source=source)
            for cmd, data in commandQueue:
                localServer.handle(cmd, data)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno,exc_obj, W)
        _print(e)


def cmd_MODE(self, localServer, recv, override=False, handleParams=None):
    #print('handleParams: {}'.format(handleParams))
    #_print('cmd_MODE localServer: {}'.format(localServer))
    _print('{} {}'.format(self, ' '.join(recv)), server=localServer)
    try:
        if type(self).__name__ == 'Server':
            originServer = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], localServer.servers))
            if not originServer:
                originServer = self
            else:
                originServer = originServer[0]
        else:
            originServer = self.server
        if type(self).__name__ == 'Server' and self != localServer:
            try:
                source = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))
                recv = recv[1:]
                target = recv[1]
                if not source:
                    source = originServer
                else:
                    source = source[0]
                if target[0] not in localServer.chantypes:
                    pass
                else:
                    channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), localServer.channels))
                    if not channel:
                        return
                    processModes(self, localServer, channel[0], recv[1:], source=source)
                    return
            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                _print(e, server=localServer)
        else:
            source = self

        recv = ' '.join(recv).split()
        chstatus = localServer.chstatus
        chmodes = ''.join(localServer.chmodes.split(',')[0:])+chstatus

        if len(recv) < 2:
            self.sendraw(461, ':MODE Not enough parameters')
            return

        elif len(recv) == 2 and recv[1][:1] in localServer.chantypes:
            channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), localServer.channels))
            if not channel:
                self.sendraw(401, '{} :No such channel'.format(recv[1]))
                return
            channel = channel[0]
            if 's' in channel.modes and self not in channel.users and not self.ocheck('o', 'override'):
                return
            params = []
            for m in channel.modes:
                if m == 'l':
                    params.append(str(channel.limit))

                elif m == 'L':
                    params.append(str(channel.redirect))

                elif m == 'f':
                    try:
                        fparams = '['
                        for t in channel.chmodef:
                            fstring = '{}:{}:{}'.format(channel.chmodef[t]['amount'],t,channel.chmodef[t]['time'])
                            if channel.chmodef[t]['action']:
                                try:
                                    fstring += ':{}:{}'.format(channel.chmodef[t]['action'], channel.chmodef[t]['duration'])
                                except Exception as ex:
                                    pass
                                    #print('t: {} -- {}'.format(t,ex))
                            fparams += fstring+','
                        fparams = fparams[:-1]
                        fparams += ']'
                        params.append(fparams)
                    except Exception as ex:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
                        _print(e, server=localServer)

                elif m == 'k':
                    params.append(channel.key)
            self.sendraw(324, '{} +{} {}'.format(channel.name, channel.modes,' '.join(params) if len(params) > 0 and (self in channel.users or 'o' in self.modes) else ''))
            self.sendraw(329, '{} {}'.format(channel.name, channel.creation))
            return

        elif recv[1][0] not in localServer.chantypes:
            user = list(filter(lambda u: u.nickname.lower() == recv[1].lower() or u.uid == recv[1], localServer.users))
            if not user:
                return

            if not localServer.ocheck('o', 'remotemode'):
                if user[0] != self and self.server == localServer:
                    return
            chgumode(self, localServer, recv, override, source=source)
            return

        ######################
        ### CHANNEL MODES ####
        ######################
        channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), localServer.channels))
        if not channel:
            self.sendraw(401, '{} :No such channel'.format(recv[1]))
            return

        channel = channel[0]
        if type(self).__name__ == 'Server' and not self.eos and self != localServer:
            return

        if type(self).__name__ != 'Server':
            if self not in channel.users and not self.ocheck('o', 'override'):
                self.sendraw(401, '{} :No such channel'.format(recv[1]))
                return

        if len(recv) == 3:
            if recv[2] == '+b' or recv[2] == 'b':
                for entry in channel.bans:
                    self.sendraw(367, '{} {} {} {}'.format(channel.name, entry, channel.bans[entry]['setter'], channel.bans[entry]['ctime']))
                self.sendraw(368, '{} :End of Channel Ban List'.format(channel.name))
                return
            elif recv[2] == '+e' or recv[2] == 'e':
                if self.chlevel(channel) < 3 and not self.ocheck('o', 'override'):
                    self.sendraw(482, '{} :You are not allowed to view the excepts list'.format(channel.name))
                    return
                for entry in channel.excepts:
                    self.sendraw(348, '{} {} {} {}'.format(channel.name, entry, channel.excepts[entry]['setter'], channel.excepts[entry]['ctime']))
                self.sendraw(349, '{} :End of Channel Exceptions List'.format(channel.name))
                return
            elif recv[2] == '+I' or recv[2] == 'I':
                if self.chlevel(channel) < 3 and not self.ocheck('o', 'override'):
                    self.sendraw(482, '{} :You are not allowed to view the invex list'.format(channel.name))
                    return
                for entry in channel.invex:
                    self.sendraw(346, '{} {} {} {}'.format(channel.name, entry, channel.invex[entry]['setter'], channel.invex[entry]['ctime']))
                self.sendraw(347, '{} :End of Channel Invite List'.format(channel.name))
                return

        if type(self).__name__ != 'Server':
            if self.chlevel(channel) < 2 and not self.ocheck('o', 'override'):
                self.sendraw(482, '{} :You\'re not a channel operator'.format(channel.name))
                return
            elif self.chlevel(channel) < 2:
                oper_override = True

        #if recv[2][0] not in '+-':
        #    self.sendraw(501, '{} :You must specify + or - for your modes'.format(self.nickname))
        #    return

        try:
            processModes(self, localServer, channel, recv[1:], source=source)
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb. tb_lineno, exc_obj)
            _print(e, server=localServer)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

def chgumode(self, localServer, recv, override, source=None):
    try:
        modes = []
        action = ''
        remoteMode = False
        target = list(filter(lambda u: u.nickname.lower() == recv[1].lower(), localServer.users))
        if not target:
            return

        target = target[0]

        if type(self).__name__ == 'Server':
            override = True
            displaySource = self.hostname
            if self != localServer:
                remoteMode = True
                if source:
                    self = source
        else:
            displaySource = self.nickname

        umodes = localServer.umodes
        warn = []
        showsno = False
        for m in str(recv[2]):
            try:
                if m in localServer.conf['settings']['modelock'] and not self.ocheck('o', 'override') and not override:
                    if 'lock' not in warn:
                        warn.append('lock')
                        localServer.broadcast([self], 'NOTICE {} :Setting/removing of usermode(s) \'{}\' has been disabled.'.format(self.nickname, localServer.conf['settings']['modelock']))
                    continue
            except:
                pass

            if m == 'r' and type(self).__name__ != 'Server':
                if self.server.hostname not in localServer.conf['settings']['ulines']:
                    continue
            if m in '+-' and action != m:
                action = m
                try:
                    if modes[-1] in '+-':
                        del modes[-1]
                except:
                    pass
                modes.append(action)
            else:
                if m in 'z' and not override:
                    if m not in warn:
                        self.sendraw(501, 'Mode +{} may only be set by servers'.format(m))
                        warn.append(m)
                    continue
                if m in 'ohsqHW' and (not self.oper or (self.operaccount and m not in localServer.conf['opers'][self.operaccount]['modes']) and not override) and not remoteMode:
                    continue
                if action == '+' and m in umodes:
                    if m == 'S' and self.server.hostname not in localServer.conf['settings']['ulines']:
                        self.sendraw(501, 'Mode +{} may only be set by servers'.format(m))
                        continue
                    if m == 's':
                        if len(recv) > 3:
                            for s in recv[3]:
                                if s in '+-':
                                    saction = s
                                    continue
                                if saction == '-' and s in target.snomasks:
                                    showsno = True
                                    target.snomasks = target.snomasks.replace(s, '')
                                    continue
                                if saction == '+' and s in localServer.snomasks and (self.operaccount and s in localServer.conf['opers'][self.operaccount]['snomasks']) and s not in target.snomasks:
                                    showsno = True
                                    target.snomasks += s
                                    continue
                    if m == '^' and not target.ocheck('o', 'stealth'):
                        continue
                    if m == '^':
                        target.stealthOn()

                    if m not in target.modes:
                        if m in 'sqHSW^' and m not in target.opermodes:
                            target.opermodes += m
                        target.modes += m
                        modes.append(m)

                if action == '-' and m in umodes and m in target.modes:
                    if m == 'S' and self.server.hostname not in localServer.conf['settings']['ulines']:
                        self.sendraw(501, 'Mode +{} may only be set by servers'.format(m))
                        continue
                    if m == 's':
                        target.snomasks = ''
                    if m == 'o':
                        target.oper = False
                        target.operflags = []
                        ### Assign a class.
                        for cls in localServer.conf['allow']:
                            clientmaskhost = '{}@{}'.format(target.ident, target.ip)
                            if 'ip' in localServer.conf['allow'][cls]:
                                clientmask = '{}@{}'.format(target.ident, target.ip)
                                isMatch = match(localServer.conf['allow'][cls]['ip'], clientmask)
                            if 'hostname' in localServer.conf['allow'][cls]:
                                clientmask = '{}@{}'.format(target.ident, target.hostname)
                                isMatch = match(localServer.conf['allow'][cls]['hostname'], clientmask)
                            if isMatch:
                                if 'options' in localServer.conf['allow'][cls]:
                                    if 'ssl' in localServer.conf['allow'][cls]['options'] and not target.ssl:
                                        continue
                                target.cls = cls

                        for mode in [m for m in target.opermodes if m in target.modes]:
                            modes.append(mode)
                            if mode == 's':
                                target.snomasks = ''
                        if target.swhois:
                            operSwhois = ''
                            if 'swhois' in localServer.conf['opers'][target.operaccount]:
                                operSwhois = localServer.conf['opers'][target.operaccount]['swhois']
                            if operSwhois in target.swhois:
                                target.swhois.remove(operSwhois)
                            if target.operswhois in target.swhois:
                                target.swhois.remove(target.operswhois)
                            data = ':{} SWHOIS {} :'.format(localServer.sid, target.uid)
                            localServer.syncToServers(localServer, target.server, data)
                            for line in target.swhois:
                                data = ':{} SWHOIS {} :{}'.format(localServer.sid, target.uid, line)
                                localServer.syncToServers(localServer, target.server, data)

                        target.opermodes = ''

                    if m == '^' and not target.ocheck('o', 'stealth'):
                        continue
                    if m == '^':
                        target.stealthOff()

                    if m not in modes:
                        modes.append(m)

                    # Removing modes from user class.
                    for mode in modes:
                        target.modes = target.modes.replace(mode, '')

        if 'o' in target.modes:
            target.modes = 'o'+target.modes.replace('o', '')
        if ' '.join(modes)[-1] in '+-':
            del modes[-1]
        modes = ''.join(modes)
        if len(modes) > 1:
            if target.socket and not remoteMode:
                target._send(':{} MODE {} :{}'.format(displaySource, target.nickname, modes))
            else:
                target._send(':{} MODE {} :{}'.format(source.nickname, target.nickname, modes))

            if source != target:
                self.sendraw(501, 'UMODE {} :{}'.format(target.nickname, modes))

            if target.server != localServer:
                target.server._send(':{} MODE {} :{}'.format(displaySource, target.nickname, modes))

            localServer.syncToServers(localServer, self.server, ':{} UMODE2 {}'.format(target.uid, modes))
        if 's' in modes or showsno:
            self.sendraw(8, 'Server notice mask (+{})'.format(target.snomasks))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
