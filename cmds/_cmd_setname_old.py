import os
import sys

def cmd_SETNAME(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))
            if not self:
                return
            ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
            self = self[0]
            recv = recv[1:]
            realname = recv[1].rstrip()
            self.realname = realname
            localServer.syncToServers(localServer, self.server, ':{} SETNAME {}'.format(self.uid, self.realname))
            return

        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return

        if len(recv) < 2:
            self.sendraw(461, ':SETNAME Not enough parameters')
            return

        self.realname = recv[1][:48].rstrip()

        self._send(':{} NOTICE {} :*** Your realname is now "{}"'.format(localServer.hostname, self.nickname, self.realname))

        localServer.syncToServers(localServer, self.server, ':{} SETNAME {}'.format(self.uid, self.realname))
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
