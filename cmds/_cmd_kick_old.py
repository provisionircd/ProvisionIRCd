W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple
import os
import sys

def cmd_KICK(self, localServer, recv, override=False):
    try:
        oper_override = False
        if type(self).__name__ == 'Server':
            if self != localServer:
                S = recv[0][1:]
                source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
                self = source[0]
                recv = recv[1:]
            override = True
        if type(self).__name__ == 'Server':
            sourceServer = self
            sourceID = self.sid
        else:
            sourceServer = self.server
            sourceID = self.uid

        if len(recv) < 3:
            self.sendraw(461, ':KICK Not enough parameters')
            return
        chan = recv[1]

        channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))

        if not channel:
            self.sendraw(401, '{} :No such channel'.format(chan))
            return

        channel = channel[0]

        if type(self).__name__ != 'Server':
            if self.chlevel(channel) < 2 and not self.ocheck('o', 'override') and not override:
                self.sendraw(482, '{} :You\'re not a channel operator'.format(channel.name))
                return
            elif self.chlevel(channel) < 2:
                oper_override = True
        # Set the userclass of the target.
        user = list(filter(lambda u: (u.nickname.lower() == recv[2].lower() or u.uid.lower() == recv[2].lower()) and '^' not in u.modes, localServer.users))

        if not user:
            self.sendraw(401, '{} :No such nick'.format(recv[2]))
            return

        user = user[0]

        if channel not in user.channels:
            self.sendraw(441, '{} :User isn\'t on that channel'.format(channel.name))
            return

        if (user.chlevel(channel) > self.chlevel(channel) or 'q' in user.modes) and not self.ocheck('o', 'override') and not override:
            self.sendraw(972, '{} :You cannot kick {}{}'.format(channel.name, user.nickname,' (+q)' if 'q' in user.modes else ''))
            return
        elif user.chlevel(channel) > self.chlevel(channel) or 'q' in user.modes:
            oper_override = True

        if 'Q' in channel.modes and self.chlevel(channel) < 5 and not self.ocheck('o', 'override') and not override:
            self.sendraw(404, '{} :KICKs are not permitted in this channel'.format(channel.name))
            return
        elif 'Q' in channel.modes and self.chlevel(channel) < 5 and not override:
            oper_override = True
        if len(recv) == 3:
            reason = self.nickname
        else:
            reason = ' '.join(recv[3:])
        if reason[0] == ':':
            reason = reason[1:]
        reason = reason[:localServer.kicklen]
        if oper_override:
            localServer.snotice('s', '*** OperOverride by {} ({}@{}) with KICK {} {} ({})'.format(self.nickname, self.ident, self.hostname, channel.name, user.nickname, reason))
        self.broadcast(channel.users, 'KICK {} {} :{}'.format(channel.name, user.nickname, reason))
        user.channels.remove(channel)
        channel.users.remove(user)
        channel.usermodes.pop(user)
        if user in channel.messageQueue:
            del channel.messageQueue[user]

        if len(channel.users) == 0:
            localServer.channels.remove(channel)

        try:
            if channel.name.lower() == localServer.conf['settings']['helpchan'].lower() and 'h' in user.modes:
                user.modes = user.modes.replace('h', '')
                localServer.syncToServers(localServer, sourceServer, ':{} UMODE2 -h'.format(user.uid))
        except:
            pass
        localServer.syncToServers(localServer, sourceServer, ':{} KICK {} {} :{}'.format(sourceID, channel.name, user.nickname, reason))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        #print(e)
