import os, sys

def cmd_SETHOST(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))
            if not self:
                return
            ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
            self = self[0]
            recv = recv[1:]
            host = str(recv[1][:64]).strip()
            self.cloakhost = host
            localServer.syncToServers(localServer,self.server,':{} SETHOST {}'.format(self.uid,self.cloakhost))
            return

        if 'o' not in self.modes:
            self.sendraw(481,':Permission denied - You are not an IRC Operator')
            return

        if len(recv) < 2:
            self.sendraw(461,':SETHOST Not enough parameters')
            return

        host = str(recv[1][:64]).strip()

        valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
        for c in str(host):
            if c.lower() not in valid:
                host = host.replace(c,'')
                #self._send(':{} NOTICE {} :*** Invalid character: {}'.format(localServer.hostname,self.nickname,c))
                #return
        self.cloakhost = host

        self._send(':{} NOTICE {} :*** Your hostname is now "{}"'.format(localServer.hostname, self.nickname, self.cloakhost))

        localServer.syncToServers(localServer, self.server,':{} SETHOST {}'.format(self.uid, self.cloakhost))
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
