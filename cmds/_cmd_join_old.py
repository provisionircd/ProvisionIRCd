from ircd import Channel
from handle.functions import match, _print
import time
import sys
import os

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

def checkMatch(self, localServer, type, channel):
    if type == 'b':
        for b in channel.bans:
            if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
                return True
            if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
                return True
            if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
                return True
            if b[:2] == '~C':
                chanBan = b.split(':')[1]
                chanBan = list(filter(lambda c: c.name.lower() == chanBan.lower(), localServer.channels))
                if chanBan:
                    if chanBan[0] in self.channels:
                        return True
            elif b[:2] == '~t':
                b = b.split(':')[2]
                if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
                    return True
                if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
                    return True
                if (match(b, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
                    return True

    if type == 'e':
        for e in channel.excepts:
            if (match(e, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
                return True
            if (match(e, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
                return True
            if (match(e, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
                return True

    if type == 'I':
        for I in channel.invex:
            if (match(I, '{}!{}@{}'.format(self.nickname, self.ident, self.hostname))):
                return True
            if (match(I, '{}!{}@{}'.format(self.nickname, self.ident, self.ip))):
                return True
            if (match(I, '{}!{}@{}'.format(self.nickname, self.ident, self.cloakhost))):
                return True

def cmd_JOIN(self, localServer, recv, override=False, sync=False, sajoin=False):
    try:
        ############################################################################################
        ### This should be at the start of every command, that requires syncing between servers. ###
        ############################################################################################
        if type(self).__name__ == 'Server':
            sourceServer = self
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
            ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
            recv = recv[1:]
            override = True
        else:
            sourceServer = self.server

        if sajoin:
            override = True

        if sourceServer == localServer or sajoin:
            ### Only sync if the join occurs on the localServer. Makes sense, right? Right...
            sync = True

        if len(recv) < 2:
            self.sendraw(461, ':JOIN Not enough parameters')
            return

        if recv[1] == '0':
            for channel in list(self.channels):
                self.handle('PART {} :Left all channels'.format(channel.name))
            return

        pc = 0
        key = None

        for chan in recv[1].split(','):
            modeless_chan, local_chan = False, False
            channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))
            if channel and channel[0] in self.channels:
                continue
            if len(recv) > 2:
                try:
                    key = recv[2:][pc]
                    pc += 1
                except:
                    pass

            if chan[0] not in localServer.chantypes and recv[0] != '0' and (sourceServer == localServer and not channel):
                self.sendraw(403, '{} :Illegal channel name'.format(chan))
                continue

            if chan[0] == '+':
                modeless_chan = True
            elif chan[0] == '&':
                local_chan = True

            if len(chan) > localServer.chanlen and (sourceServer == localServer and not channel):
                self.sendraw(485, '{} :Channel too long'.format(chan))
                continue

            valid = "abcdefghijklmnopqrstuvwxyz0123456789`~!@#$%^&*()-=_+[]{}\\|;':\"./<>?"
            for c in chan:
                if c.lower() not in valid and (sourceServer == localServer and not channel):
                    self.sendraw(479, '{} :Illegal channel name'.format(chan))
                    continue
            if not channel:
                new = Channel(chan)
                localServer.channels.append(new)
                channel = [new]
            channel = channel[0]

            continueLoop = False
            if not override:
                for c in self.channels:
                    for b in [b for b in c.bans if b[:2] == '~C']:
                        banChan = b.split(':')[1]
                        if banChan.lower() == channel.name.lower() and not self.ocheck('o', 'override') and not checkMatch(self, localServer, 'e', channel):
                            self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                            continueLoop = True
                            continue

                if continueLoop:
                    continueLoop = False
                    continue

                invite_override = False
                if self in channel.invites:
                    invite_override = channel.invites[self]['override']

                if 'O' in channel.modes and 'o' not in self.modes:
                    self.sendraw(520, '{} :Cannot join channel (IRCops only)'.format(channel.name))
                    continue

                if 'R' in channel.modes and 'r' not in self.modes and not invite_override:
                    self.sendraw(477, '{} :You need a registered nick to join that channel'.format(channel.name))
                    continue

                if 'z' in channel.modes and 'z' not in self.modes and not invite_override:
                    self.sendraw(489, '{} :Cannot join channel (not using a secure connection)'.format(channel.name))
                    continue

                if checkMatch(self,localServer,'b',channel) and not checkMatch(self, localServer, 'e', channel) and not invite_override:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    continue

                if channel.limit != 0 and len(channel.users) >= channel.limit and not invite_override:
                    if channel.redirect:
                        self.handle('JOIN', channel.redirect)
                        self.sendraw(471, '{} :Channel is full so you are redirected to {}'.format(channel.name, channel.redirect))
                        continue

                    self.sendraw(471, '{} :Cannot join channel (+l)'.format(channel.name))
                    continue

                if channel.key and key != channel.key and not invite_override:
                    self.sendraw(475, '{} :Cannot join channel (+k)'.format(channel.name))
                    continue

                if 'i' in channel.modes and self not in channel.invites and not checkMatch(self, localServer, 'I', channel) and not invite_override:
                    self.sendraw(473, '{} :Cannot join channel (+i)'.format(channel.name))
                    continue

            if not channel.users and (self.server.eos or self.server == localServer) and not modeless_chan:
                channel.usermodes[self] = 'o'

            else:
                channel.usermodes[self] = ''
            channel.users.append(self)
            self.channels.append(channel)
            if self in channel.invites:
                del channel.invites[self]

            if '^' in self.modes:
                users = (user for user in channel.users if user.ocheck('o', 'stealth'))
                #print(users)
                self.broadcast(users, 'JOIN :{}'.format(channel.name))
                localServer.broadcast(users, 'MODE {} +y {}'.format(channel.name, self.nickname))

            else:
                self.broadcast(channel.users, 'JOIN :{}'.format(channel.name))

            ### If you notice issues with missing @ on first join, uncomment this. But theoretically, this should not happen.
            #if channel.users == [self] and (self.server.eos or self.server == localServer) and not modeless_chan:
            #    _print('Assigning +o -- 2')
            #    channel.usermodes[self] = 'o'
            if channel.topic_time != 0:
                self.handle('TOPIC', channel.name)
            self.handle('NAMES', channel.name)

            prefix = ''
            for u in channel.usermodes[self]:
                if u == 'q':
                    prefix += '*'
                if u == 'a':
                    prefix += '~'
                if u == 'o':
                    prefix += '@'
                if u == 'h':
                    prefix += '%'
                if u == 'v':
                    prefix += '+'

            if 'j' in channel.chmodef and self.server == localServer: # and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override
                r = int(round(time.time() * 1000))
                channel.joinQueue[r] = {}
                channel.joinQueue[r]['ctime'] = int(time.time())
                if len(channel.joinQueue) > channel.chmodef['j']['amount']:
                    ### What should we do?
                    channel.joinQueue = {}
                    if channel.chmodef['j']['action'] == 'i':
                        localServer.handle('MODE', '{} +i'.format(channel.name))
                    elif channel.chmodef['j']['action'] == 'R':
                        localServer.handle('MODE', '{} +R'.format(channel.name))
                    channel.chmodef['j']['actionSet'] = int(time.time())
                    continue

            if sync and not local_chan:
                #print('JOIN command from: {}'.format(sourceServer.hostname))
                timestamp = channel.creation
                ### Unreal: [Aug 13 17:44:26.938980 2018] Debug: Received: :072 SJOIN 1534175060 #secret :072PK4V01
                ### Provision: [Aug 13 17:50:57.973390 2018] Debug: Received: :001 SJOIN 1534175457 #secret :@001US1YZQ
                localServer.syncToServers(localServer, sourceServer, ':{} SJOIN {} {}{} :{}{}'.format(self.server.sid, timestamp, channel.name, ' +{}'.format(channel.modes) if channel.modes and channel.users == [self] else '', prefix, self.uid))

            if self.server != localServer and self.server.eos and not local_chan:
                self.server._send(':{} JOIN {}'.format(self.uid, channel.name))

            if channel.users == [self] and not modeless_chan:
                localServer.handle('MODE', '{} +nt'.format(channel.name))

            #if self.server.hostname != localServer.conf['settings']['ulines']:
            #    if self.server != localServer and not sourceServer.eos:
            #        pass
            #    elif '^' not in self.modes:
            #        msg = '*** {} ({}@{}) has joined channel {}'.format(self.nickname,self.ident,self.hostname,channel.name)
            #        localServer.snotice('j',msg)

            #print('User refcount after join: {}'.format(sys.getrefcount(self)))
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)
