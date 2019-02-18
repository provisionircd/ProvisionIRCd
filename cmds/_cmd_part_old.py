import os
import sys
import time

def cmd_PART(self, localServer, recv, reason=None):
    ############################################################################################
    ### This should be at the start of every command, that requires syncing between servers. ###
    ############################################################################################
    if type(self).__name__ == 'Server':
        self = list(filter(lambda u: u.uid == recv[0][1:], localServer.users))[0]
        ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
        recv = recv[1:]

    try:
        if len(recv) < 2:
            self.sendraw(461, ':PART Not enough parameters')
            return

        if not reason:
            if len(recv) > 2:
                reason = ' '.join(recv[2:])
                if reason.startswith(':'):
                    reason = reason[1:]
                reason = ':{}'.format(reason)
            else:
                reason = ''

            reason = reason.rstrip()

        if 'static-part' in localServer.conf['settings'] and localServer.conf['settings']['static-part']:
            reason = localServer.conf['settings']['static-part']

        for chan in recv[1].split(','):
            channel = list(filter(lambda c: c.name.lower() == chan.lower(), localServer.channels))
            if not channel:
                self.sendraw(442,'{} :You\'re not on that channel'.format(chan))
                continue

            channel = channel[0]
            self.channels.remove(channel)
            channel.usermodes.pop(self)
            channel.users.remove(self)
            if len(channel.users) == 0:
                localServer.channels.remove(channel)

            if '^' in self.modes:
                users = (user for user in channel.users if user.ocheck('o', 'stealth'))
                #localServer.broadcast(users,'MODE {} -y {}'.format(channel.name,self.nickname))
                self.broadcast(users, 'PART {} :{}'.format(channel.name, reason))
            else:
                self.broadcast(channel.users+[self], 'PART {} {}'.format(channel.name, reason))

            try:
                if channel.name.lower() == localServer.conf['settings']['helpchan'].lower() and 'h' in self.modes and 'o' not in self.modes:
                    self.modes = self.modes.replace('h','')
                    localServer.syncToServers(localServer, self.server, ':{} UMODE2 -h'.format(self.uid))
            except:pass

            #if self.server.hostname != localServer.conf['settings']['ulines'] and '^' not in self.modes:
            #    msg = '*** {} ({}@{}) has left channel {}'.format(self.nickname,self.ident,self.hostname,channel.name)
            #    localServer.snotice('j',msg)

            if chan[0] != '&':
                localServer.syncToServers(localServer,self.server,':{} PART {} {}'.format(self.uid, channel.name, reason))


    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)
