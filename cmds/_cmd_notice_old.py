import time
import os
import sys
from handle.functions import checkSpamfilter

def cmd_NOTICE(self, localServer, recv, override=False):
    try:
        if type(self).__name__ == 'Server':
            override = True
            if self != localServer:
                S = recv[0][1:]
                source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
                if source:
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
            return self.sendraw(411, ':No recipient given')

        elif len(recv) < 3:
            return self.sendraw(412, ':No text to send')

        targets = recv[1].split(',')
        msg = ' '.join(recv[2:])

        for target in targets[:localServer.maxtargets]:
            sync = True
            if target[0] not in localServer.chantypes and target[0] != '$':
                user = list(filter(lambda u: u.nickname.lower() == target.lower() or u.uid.lower() == target.lower(), localServer.users))
                if not user:
                    self.sendraw(401, '{} :No such user'.format(target))
                    continue

                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, user[0].nickname, 'private', msg):
                    continue

                if user[0].server == localServer:
                    sync = False

                self.broadcast(user, 'NOTICE {} :{}'.format(user[0].nickname, msg))

                if sync:
                    localServer.syncToServers(localServer, sourceServer, ':{} NOTICE {} :{}'.format(sourceID, target, msg))

                if type(self).__name__ == 'User':
                    self.idle = int(time.time())

            elif target[0] == '$' and sourceServer != localServer:
                server = list(filter(lambda s: s.hostname.lower() == target[1:].lower(), localServer.servers+[localServer]))[0]
                if server == localServer:
                    for user in (user for user in localServer.users if user.server == server):
                        self.broadcast([user], 'NOTICE ${} :{}'.format(server.hostname.lower(), msg))
                else:
                    for s in (s for s in localServer.servers if s != sourceServer):
                        s._send(':{} NOTICE ${} :{}'.format(sourceID, server.hostname.lower(), msg))

            else:
                channel = list(filter(lambda c: c.name.lower() == target.lower(), localServer.channels))

                if not channel:
                    self.sendraw(401, '{} :No such channel'.format(target))
                    continue

                channel = channel[0]

                if self not in channel.users and 'n' in channel.modes and not self.ocheck('o', 'override') and not override:
                    self.sendraw(404, '{} :No external messages'.format(channel.name))
                    continue

                if 'T' in channel.modes and self.chlevel(channel) < 3 and not self.ocheck('o', 'override') and not override:
                    self.sendraw(404, '{} :NOTICEs are not permitted in this channel'.format(channel.name))
                    continue

                if type(self).__name__ == 'User' and checkSpamfilter(self, localServer, channel.name, 'channel', msg):
                    continue

                self.broadcast([user for user in channel.users], 'NOTICE {} :{}'.format(channel.name, msg))

                if type(self).__name__ == 'User':
                    self.idle = int(time.time())

                if sync:
                    localServer.syncToServers(localServer, sourceServer, ':{} NOTICE {} :{}'.format(sourceID, target, msg))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname, exc_tb.tb_lineno, exc_obj)
        print(e)
