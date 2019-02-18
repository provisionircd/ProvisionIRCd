import os, sys, time, re
from ircd import Channel
import handle.handleLogs as Logger

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

from modules.m_mode import processModes

def _print(txt):
    Logger.write(txt)
    #print(txt)

def cmd_SJOIN(self, localServer, recv):
    try:
        if type(self).__name__ != 'Server':
            self.sendraw(487, ':SJOIN is a server only command')
            return
        raw = ' '.join(recv)
        source = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], localServer.servers))
        if not source:
            return

        source = source[0]

        '''
        ###  :001 SJOIN 1517104099 #Home +nt :@001O9SM99RJ
        channel = list(filter(lambda c: c.name.lower() == recv[3].lower(), localServer.channels))
        if channel:
            timestamp = channel[0].creation
        else:
            timestamp = int(time.time())
        currentTimeSJOIN = '{} {} {}'.format(' '.join(recv[:2]),timestamp,' '.join(recv[3:]))
        if source.eos:
            print('Source {} is done syncing, so sending current timestamp with SJOIN message.'.format(source.hostname))
            raw = currentTimeSJOIN
        '''
        channel = recv[3]
        if channel[0] == '&':
            print('{}ERROR: received a local channel from remote server: {}{}'.format(R, channel, W))
            return

        if not source.allowUidSjoinSync:
            if not localServer.forked:
                print('Experimental: Server {} is not introduced yet, temporaring storing SJOIN data.')
            source.tempSync.append(raw)
        else:
            localServer.syncToServers(localServer, self,raw)


        #if self.eos:
        #for s in [s for s in localServer.servers if s != localServer and s != self]:
        #    print('{}Syncing remote channel {} to {}{}'.format(G,recv[3],s.hostname,W))
        #    s._send('{}'.format(raw))

        memberlist = ' '.join(' '.join(recv).split(':')[2:]).split('&')[0].split('"')[0].split("'")[0].split()

        banlist, excepts, invex = [], [], []
        try:
            banlist = ' '.join(recv).split('&')[1].split('"')[0].split()
        except:
            pass
        try:
            excepts = ' '.join(recv).split('"')[1].split("'")[0].split()
        except:
            pass
        try:
            invex = ' '.join(recv).split("'")[1].split()
        except:
            pass
        timestamp = int(recv[2])

        if recv[4].startswith('+'):
            modes = recv[4].replace('+','')
        else:
            modes = ''

        giveModes = []
        giveParams = []

        removeModes = []
        removeParams = []

        modeDisplay, paramDisplay = [], []

        pc = 5
        for m in modes:
            if m == 'k':
                key = recv[pc]
                pc += 1
            if m == 'l':
                limit = recv[pc]
                pc += 1

        for member in memberlist:
            membernick = []
            for c in member:
                if c not in '*~@%+':
                    membernick.append(c)
            membernick = ''.join(membernick)

            ### It is possible that 'membernick' is a UID. Let's check if that's the case.

            userClass = list(filter(lambda c: c.nickname.lower() == membernick.lower() or c.uid == membernick, localServer.users))
            if not userClass:
                if not localServer.forked:
                    print('{}ERROR: could not fetch userclass for remote user {}. Looks like the user did not sync correctly.{}'.format(R, membernick, W))
                continue
            else:
                userClass = userClass[0]
            p = {'override': True}
            userClass.handle('join', channel, params=p)
            localChan = list(filter(lambda c: c.name.lower() == channel.lower(), localServer.channels))[0]
            if userClass.server != localServer:
                if not localServer.forked:
                    print('{}External user {} joined {} on local server.{}'.format(G, userClass.nickname, channel, W))
            if timestamp < localChan.creation and not source.eos:
                if '*' in member:
                    giveModes.append('q')
                    giveParams.append(userClass.nickname)
                if '~' in member:
                    giveModes.append('a')
                    giveParams.append(userClass.nickname)
                if '@' in member:
                    giveModes.append('o')
                    giveParams.append(userClass.nickname)
                if '%' in member:
                    giveModes.append('h')
                    giveParams.append(userClass.nickname)
                if '+' in member:
                    giveModes.append('v')
                    giveParams.append(userClass.nickname)

        if timestamp < localChan.creation and not source.eos:
            ### Changed self.eos to source.eos
            finalModes = ' '.join(recv[3:]).split(':')[0].split()[0]
            for p in finalModes.split()[1:]:
                giveParams.append(p)

            # Remote channel is dominant. Replacing modes with remote channel
            # Clear the local modes.
            #
            if not localServer.forked:
                print('Remote channel is dominant. Replacing modes with remote channel')
            localChan.creation = timestamp
            if modes:
                for m in localChan.modes:
                    if m not in modes and m != 'k':
                        removeModes.append(m)
                        continue
                    if m == 'k' and key != localChan.key:
                        removeParams.append(localChan.key)
                        removeModes.append(m)
                    elif m == 'l' and limit != localChan.limit:
                        removeParams.append(localChan.limit)
                        removeModes.append(m)

                for m in modes:
                    if m not in localChan.modes:
                        giveModes.append(m)

            # Removing local channel user modes.
            for user in localChan.users:
                #if user is userClass:
                #    continue
                for m in localChan.usermodes[user]:
                    removeModes.append(m)
                    removeParams.append(user.nickname)

            #pc = 5
            for m in modes:
                if m == 'k':
                    #key = recv[pc]
                    giveParams.append(key)
                    #pc += 1
                if m == 'limit':
                    #limit = recv[pc]
                    giveParams.append(limit)
                    #pc += 1

            for b in banlist:
                giveModes.append('b')
                giveParams.append(b)

            for e in excepts:
                giveModes.append('e')
                giveParams.append(e)

            for I in invex:
                giveModes.append('I')
                giveParams.append(I)

            data = []
            data.append(localChan.name)
            modes = '{}{}'.format('-'+''.join(removeModes) if removeModes else '','+'+''.join(giveModes) if giveModes else '')
            data.append(modes)
            for p in removeParams:
                data.append(p)
            for p in giveParams:
                data.append(p)

            processModes(self, localServer, localChan, data, sync=True, source=source)

        elif timestamp == localChan.creation and not source.eos:
            if modes:
                _print('{}Equal timestamps for remote channel {} -- merging modes.{}'.format(Y, localChan.name, W))
                for member in memberlist:
                    rawUid = re.sub('[:*!~&@%+]', '', member)
                    if '*' in member:
                        giveModes.append('q')
                        giveParams.append(rawUid)
                    if '~' in member:
                        giveModes.append('a')
                        giveParams.append(rawUid)
                    if '@' in member:
                        giveModes.append('o')
                        giveParams.append(rawUid)
                    if '%' in member:
                        giveModes.append('h')
                        giveParams.append(rawUid)
                    if '+' in member:
                        giveModes.append('v')
                        giveParams.append(rawUid)

                for m in modes:
                    if m not in localChan.modes:
                        giveModes.append(m)
                    if m == 'k':
                        giveParams.append(key)
                    if m == 'l':
                        giveParams.append(limit)

                for b in [b for b in banlist if b not in localChan.bans]:
                    giveModes.append('b')
                    giveParams.append(b)

                for e in [e for e in excepts if e not in localChan.excepts]:
                    giveModes.append('e')
                    giveParams.append(e)

                for I in [I for I in invex if I not in localChan.invex]:
                    giveModes.append('I')
                    giveParams.append(I)

                data = []
                data.append(localChan.name)
                modes = '{}'.format('+'+''.join(giveModes) if giveModes else '')
                data.append(modes)
                for p in removeParams:
                    data.append(p)
                for p in giveParams:
                    data.append(p)

                processModes(self, localServer, localChan, data, sync=True, source=source)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)
