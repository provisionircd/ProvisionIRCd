"""
support for extended bans
"""

# ~T - text bans: block, replace, online.
#      block and replace speak for themselves. online follows an integer.
#      ~T:online:10 - can only send to the channel if on channel longer than 10 seconds. Can help prevent spam.
#
# ~t - timed bans: ~t:host:10 - bans for 10 minutes.
#
# ~c - channel bans.
#      +b ~c:#warez - bans everyone from channel #warez to join your channel.
#      +I ~c:@#warez - ops or higher from channel #warez can bypass +i.
#      +e ~c:@#warez - ops or higher from channel #warez can bypass +b.
#
# ~b - extended normal bans.
#      +b ~b:R:*!*@annoying.host - bans *!*@annoying.host from the channel, unless the user has a registered nick.
#                                  this allows for more control against annoying users that keep requesting new IPs from their ISP,
#                                  forcing them to log in to NickServ before joining the channel.

import ircd
import time
import re

from modules.m_mode import makeMask
from modules.m_joinpart import checkMatch

from handle.functions import match, logging

ext_bans = ['T', 't', 'c', 'O', 'a', 'b']
prefix = '~'

def checkExtMatch(type, action, channel, msg):
    try:
        if type == 'b':
            replaceDone, did_replace = False, False
            tempMsg = msg
            regex = re.compile('\x1d|\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?', re.UNICODE)
            for ban in [ban for ban in channel.bans if ban[:2] == '~T' and ban.split(':')[1] == action]:
                m = ban.split(':', 2)[2]
                m = regex.sub('', m)
                rep_char_block = None
                try:
                    int(ban.split(':')[3]) > 0
                    rep_char_block = ban.split(':')[3]
                except:
                    pass
                if action == 'block':
                    char = m.split(':')[0]
                    if rep_char_block and char_repeat(msg, char, rep_char_block):
                        return True
                    block = match(m.lower(), msg.lower()) or m.lower() in msg.lower().split()
                    if not rep_char_block and block:
                        return True
                if action == 'replace':
                    ### This just works, so don't mess it up.
                    m = ban.split(':', 2)[2]
                    if m.startswith(':'):
                        search = ':'+m.split(':')[1]
                        replaceWith = m.split(':', 2)[2]
                    else:
                        search = m.split(':')[0]
                        if m.split(':')[1] != '':
                            replaceWith = m.split(':')[1]
                        else:
                            replaceWith = ':'+m.split(':', 2)[2]
                    for word in msg.split():
                        word = regex.sub('', word)
                        tempWord = word.lower()
                        if match(search.lower(),tempWord) or search.lower() == tempWord:
                            temp = search.replace('*', '')
                            if word.isupper():
                                temp = temp.upper()
                                did_replace = True
                                replaceWith = replaceWith.upper()
                            elif not word.islower():
                                temp = re.search(temp, word, flags=re.IGNORECASE).group()
                            did_replace = True
                            tempMsg = tempMsg.replace(temp, replaceWith)
                    if did_replace:
                        replaceDone = True

            if replaceDone:
                return tempMsg
    except Exception as ex:
        logging.exception(ex)

def char_repeat(string, char, amount):
    for word in [word for word in string.split(' ') if '://' not in word and 'www.' not in word]: ### Excluding urls.
        if char == '*':
            for c in 'abcdefghijklmnopqrstuwvwxyz,.?!1234567890:':
                if word.lower().count(c.lower()) >= int(amount):
                    return True
        else:
            if word.count(char.lower()) >= int(amount):
                return True
    return False

@ircd.Modules.hooks.loop()
def checkExpiredBans(localServer):
    remove_bans = {}
    for chan in localServer.channels:
        remove_bans[chan] = []
        for ban in [ban for ban in chan.bans if ban and ban[:2] == '~t']:
            minutes = int(ban.split(':')[1]) * 60
            banset = int(chan.bans[ban]['ctime'])
            if int(time.time()) >= (minutes + banset):
                remove_bans[chan].append(ban)
    for chan in remove_bans:
        if len(remove_bans[chan]) < 1:
            continue
        bans = ' '.join(remove_bans[chan])
        tmodes = 'b'*len(remove_bans[chan])
        localServer.handle('MODE', '{} -{} {} 0'.format(chan.name, tmodes, bans))


@ircd.Modules.support(('EXTBAN='+prefix+','+str(''.join(ext_bans)), True)) ### (support string, boolean if support must be sent to other servers)
@ircd.Modules.hooks.pre_local_chanmode()
@ircd.Modules.hooks.pre_remote_chanmode()
#def extbans(self, localServer, channel, modes, params, modebuf, parambuf):
def extbans(self, localServer, channel, modebuf, parambuf, action, m, param):
    try:
        if m not in 'beI' or action != '+':
            return
        if not param:
            logging.error('ERROR: invalid param received for {}{}: {}'.format(action, m, param))
            return
        if not re.findall("(^{}[{}]):(.*)".format(prefix, ''.join(ext_bans)), param):
            #logging.info('Param {} is invalid for {}{}'.format(param, action, m))
            return

        logging.info('Param for {}{} set: {}'.format(action, m, param))

        try:
            setter = self.fullmask()
        except:
            setter = self.hostname

        if m == 'b':
            if param[:2] not in ['~T', '~c', '~t', '~b']:
                return
            if param[:2] == '~T':
                ### Text block.
                if param.split(':')[1] not in ['block', 'replace'] or len(param.split(':')) < 3:
                    return
                bAction = param.split(':')[1]
                if not param.split(':')[2:][0]:
                    return
                if bAction == 'replace':
                    ### Replace requires an additional parameter: ~T:replace:match:replacement
                    if len(param.split(':')) < 4:
                        return
                    if not param.split(':')[3]:
                        return
            elif param[:2] == '~c':
                ### Channel block.
                if len(param.split(':')) < 2:
                    return
                chanBan = param.split(':')[1]
                if chanBan[0] not in localServer.chantypes or chanBan[0] not in '+%@&~':
                    logging.info('Channel {} is invalid for {}{} {}'.format(chanBan, action, m, param))
                    return
                tempchan = list(filter(lambda c: c.name.lower() == chanBan.lower(), localServer.channels))
                if tempchan and len(channel.users) > 2:
                    tempchan = tempchan[0]
                    ### tempchan users are forbidden on channel.
                    for user in [user for user in channel.users if tempchan in user.channels and user.chlevel(channel) < 2 and not user.ocheck('o', 'override') and not checkMatch(user, localServer, 'e', channel)]:
                        cmd = ('KICK', '{} {} :Users from {} are not welcome here'.format(channel.name, user.nickname, tempchan.name))
                        commandQueue.append(cmd)

            elif param[:2] == '~t':
                ### Timed bans.
                if len(param.split(':')) < 3:
                    return
                bTime = param.split(':')[1]
                if not bTime.isdigit():
                    return
                banmask = makeMask(localServer, param.split(':')[2])
                param = '{}:{}'.format(':'.join(param.split(':')[:2]), banmask)

            elif param[:2] == '~b':
                ### Extension on normal bans.
                if len(param.split(':')) < 3:
                    return
                bParam = param.split(':')[1]
                if bParam not in ['R']:
                    return
                banmask = makeMask(localServer, param.split(':')[2])
                param = '{}:{}'.format(':'.join(param.split(':')[:2]), banmask)

        elif m == 'I':
            if param[:2] == '~O':
                if len(param.split(':')) < 2:
                    return

        if m == 'b':
            c = channel.bans
        elif m == 'I':
            c = channel.invex
        elif m == 'e':
            c = channel.excepts
        if param not in c:
            modebuf.append(m)
            parambuf.append(param)
            c[param] = {}
            c[param]['setter'] = setter
            c[param]['ctime'] = int(time.time())

    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.pre_local_join()
def join(self, localServer, channel, **kwargs):
    try:
        if 'override' in kwargs:
            logging.debug('Skipping extban checks: override')
            return (1, [])
        overrides = []
        invite_override = 0
        if self in channel.invites:
            invite_override = channel.invites[self]['override']
        for c in self.channels:
            for b in [b for b in channel.bans if b[:2] == '~c']:
                banChan = b.split(':')[1]
                ison_banchan = [chan for chan in localServer.channels if chan.name.lower() == banChan.lower() and self in chan.users]
                if (banChan.lower() == channel.name.lower() or ison_banchan) and not invite_override and not checkMatch(self, localServer, 'e', channel):
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (0, overrides)

            for b in [b for b in c.bans if b[:2] == '~c']:
                banChan = b.split(':')[1]
                ison_banchan = [chan for chan in localServer.channels if chan.name.lower() == banChan.lower() and self in chan.users]
                if (banChan.lower() == channel.name.lower() or ison_banchan) and not invite_override and not checkMatch(self, localServer, 'e', channel):
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (0, overrides)

        for b in [b for b in channel.bans if b[:2] == '~t' and not invite_override and not checkMatch(self, localServer, 'e', channel)]:
            mask = b.split(':')[2]
            ban = 0
            if (match(mask, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
                ban = 1
            if (match(mask, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
                ban = 1
            if (match(mask, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
                ban = 1
            if ban:
                self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                return (0, overrides)

        for i in channel.invex:
            if i.startswith('~O'):
                oper_class = i.split(':')[1]
                if 'i' in channel.modes and ('o' in self.modes and (hasattr(self, 'operclass') and match(oper_class, self.operclass))) and 'i' not in overrides:
                    overrides.append('i')
            if i.startswith('~a'):
                account = i.split(':')[1]
                if 'i' in channel.modes and ('r' in self.modes and (hasattr(self, 'svid') and match(account, self.svid))) and 'b' not in overrides:
                    overrides.append('i')
            if i.startswith('~c'):
                chan_ban = i.split(':')[1]
                prefix = chan_ban[0] if chan_ban[0] in '+%@&~' else ''
                chan_ban = re.sub('[:*!~&@%+]', '', chan_ban)
                chan_ban_class = [c for c in localServer.channels if c.name.lower() == chan_ban.lower()]
                if chan_ban_class and 'i' not in overrides:
                    chan_ban_class = chan_ban_class[0]
                    if prefix == '+' and self.chlevel(chan_ban_class) >= 1:
                        overrides.append('i')
                    elif prefix == '%' and self.chlevel(chan_ban_class) >= 2:
                        overrides.append('i')
                    elif prefix == '@' and self.chlevel(chan_ban_class) >= 3:
                        overrides.append('i')
                    elif prefix == '&' and self.chlevel(chan_ban_class) >= 4:
                        overrides.append('i')
                    elif prefix == '~' and self.chlevel(chan_ban_class) >= 5:
                        overrides.append('i')

        for e in channel.excepts:
            if e.startswith('~a'):
                account = e.split(':')[1]
                if ('r' in self.modes and (hasattr(self, 'svid') and match(account, self.svid))) and 'b' not in overrides:
                    overrides.append('b')
            if e.startswith('~c'):
                chan_ban = e.split(':')[1]
                prefix = chan_ban[0] if chan_ban[0] in '+%@&~' else ''
                chan_ban = re.sub('[:*!~&@%+]', '', chan_ban)
                chan_ban_class = [c for c in localServer.channels if c.name.lower() == chan_ban.lower()]
                if chan_ban_class and 'b' not in overrides:
                    chan_ban_class = chan_ban_class[0]
                    if prefix == '+' and self.chlevel(chan_ban_class) >= 1:
                        overrides.append('b')
                    elif prefix == '%' and self.chlevel(chan_ban_class) >= 2:
                        overrides.append('b')
                    elif prefix == '@' and self.chlevel(chan_ban_class) >= 3:
                        overrides.append('b')
                    elif prefix == '&' and self.chlevel(chan_ban_class) >= 4:
                        overrides.append('b')
                    elif prefix == '~' and self.chlevel(chan_ban_class) >= 5:
                        overrides.append('b')

        for b in channel.bans:
            if b.startswith('~a'):
                account = b.split(':')[1]
                if ('r' in self.modes and (hasattr(self, 'svid') and match(account, self.svid))) and 'b' not in overrides:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, overrides)
            if b.startswith('~b'):
                exemp = b.split(':')[1]
                host = b.split(':')[2]
                if match(host, self.fullmask()) and (exemp == 'R' and 'r' not in self.modes and 'b' not in overrides):
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, overrides)

        return (True, overrides)

    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.pre_chanmsg()
def pre_chanmsg(self, localServer, channel, msg):
    if checkExtMatch('b', 'block', channel, msg) and self.chlevel(channel) < 3 and not self.ocheck('o', 'override'):
        self.sendraw(404, '{} :Cannot send to channel (+b ~T)'.format(channel.name))
        return 0
    if checkExtMatch('b', 'replace', channel, msg) and self.chlevel(channel) < 5 and not self.ocheck('o', 'override'):
        msg = checkExtMatch('b', 'replace', channel, msg)
    return msg
