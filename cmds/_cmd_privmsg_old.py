from handle.functions import match, checkSpamfilter, _print

import time
import os
import sys
import re

msg = ''

#path = os.path.abspath(__file__)
#dir_path = os.path.dirname(path)
#os.chdir(dir_path)

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

def checkMatch(self, type, action, channel, msg):
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
                    word = regex.sub("",word)
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

def cmd_PRIVMSG(self, localServer, recv, override=False):
    try:
        if type(self).__name__ == 'Server':

            override = True
            if self != localServer:
                S = recv[0][1:]
                source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
                self = source[0]
                recv = recv[1:]
            recv = localServer.parse_command(' '.join(recv[0:]))

        if type(self).__name__ == 'Server':
            sourceServer = self
            sourceID = self.sid
        else:
            sourceServer = self.server
            sourceID = self.uid

        if len(recv) < 2:
            self.sendraw(411, ':No recipient given')
            return
        elif len(recv) < 3:
            self.sendraw(412, ':No text to send')
            return

        targets = recv[1].split(',')
        global msg
        msg = ' '.join(recv[2:]).rstrip()

        for target in targets[:localServer.maxtargets]:
            sync = True
            if target[0] not in localServer.chantypes:
                _print('{} :: {}'.format(self, ' '.join(recv)))
                user = list(filter(lambda u: u.nickname.lower() == target.lower() or u.uid.lower() ==target.lower(), localServer.users))

                if not user:
                    self.sendraw(401, '{} :No such nick'.format(target))
                    continue

                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, user[0].nickname, 'private', msg):
                    continue

                if user[0].server == localServer:
                    sync = False

                ### Check for module events.
                success = True
                for callable in [callable for callable in localServer.events if callable[0].lower() == recv[0].lower()]:
                    ### (command, function, module)
                    localServer.modulename = callable[2].__name__
                    try:
                        success = callable[1](self, user, msg)
                    except Exception as ex:
                        _print(ex)
                if not success:
                    continue

                if user[0].away:
                    self.sendraw(301, '{} :{}'.format(user[0].nickname, user[0].away))

                self.broadcast(user, 'PRIVMSG {} :{}'.format(user[0].nickname, msg))
                self.idle = int(time.time())

                if sync:
                    localServer.syncToServers(localServer, sourceServer, ':{} PRIVMSG {} :{}'.format(sourceID, user[0].nickname, msg))

            else:
                channel = [channel for channel in localServer.channels if channel.name.lower() == target.lower()]

                if not channel:
                    self.sendraw(401, '{} :No such channel'.format(target))
                    continue

                channel = channel[0]
                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, channel.name, 'channel', msg):
                    continue

                if not override:
                    if self not in channel.users and 'n' in channel.modes and not self.ocheck('o', 'override') and not override:
                        self.sendraw(404, '{} :No external messages'.format(channel.name))
                        continue

                    if 'C' in channel.modes and msg[0] == '' and msg[-1] == '' and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override:
                        self.sendraw(404, '{} :CTCPs are not permitted in this channel'.format(channel.name))
                        continue

                    if 'm' in channel.modes and self.chlevel(channel) == 0 and not self.ocheck('o', 'override') and not override:
                        self.sendraw(404, '{} :Cannot send to channel (+m)'.format(channel.name))
                        continue

                    if checkMatch(self, 'b', 'block', channel, msg) and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override:
                        self.sendraw(404, '{} :Cannot send to channel (+b ~T)'.format(channel.name))
                        continue

                    if checkMatch(self, 'b', 'replace', channel, msg) and self.chlevel(channel) < 4 and not self.ocheck('o', 'override') and not override:
                        msg = checkMatch(self, 'b', 'replace', channel, msg)

                if '^' in self.modes:
                    self.sendraw(404, '{} :You are invisible on channel {}'.format(channel.name, channel.name))
                    continue
                ### Check for module events.
                success = True
                for callable in [callable for callable in localServer.events if callable[0].lower() == recv[0].lower()]:
                    ### (command, function, module)
                    localServer.modulename = callable[2].__name__
                    try:
                        success = callable[1](self, channel, msg)
                    except Exception as ex:
                        _print(ex)
                if not success:
                    continue

                user = [user for user in channel.users if user != self]

                self.broadcast(user, 'PRIVMSG {} :{}'.format(channel.name, msg))
                self.idle = int(time.time())
                if 'm' in channel.chmodef and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override:
                    if self not in channel.messageQueue:
                        channel.messageQueue[self] = {}
                        channel.messageQueue[self]['ctime'] = time.time()
                    channel.messageQueue[self][int(round(time.time() * 1000))] = None
                    if len(channel.messageQueue[self]) > channel.chmodef['m']['amount']:
                        if channel.chmodef['m']['action'] == 'kick':
                            localServer.handle('KICK', '{} {} :Flood! Limit is {} messages in {} seconds.'.format(channel.name, self.uid, channel.chmodef['m']['amount'], channel.chmodef['m']['time']))
                        elif channel.chmodef['m']['action'] == 'b':
                            duration = channel.chmodef['m']['duration']
                            localServer.handle('MODE', '{} +b ~t:{}:*@{}'.format(channel.name,duration,self.cloakhost))
                            localServer.handle('KICK', '{} {} :Flood! Limit is {} messages in {} seconds.'.format(channel.name, self.uid, channel.chmodef['m']['amount'], channel.chmodef['m']['time']))
                        continue

                if sync:
                    localServer.syncToServers(localServer, sourceServer, ':{} PRIVMSG {} :{}'.format(sourceID, target, msg))
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
