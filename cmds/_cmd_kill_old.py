import os
import sys
import time
import threading

def cmd_KILL(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            ### Servers can override kill any time.
            target = list(filter(lambda u: u.nickname.lower() == recv[2].lower() or u.uid.lower() == recv[2].lower(), localServer.users))
            if not target:
                return
            quitmsg = ' '.join(recv[3:])[1:]
            reason = ' '.join(recv[8:])[1:][:-1]
            path = list(filter(lambda u: u.nickname.lower() == recv[0][1:].lower() or u.uid.lower() == recv[0][1:].lower(), localServer.users))
            if not path:
                path = list(filter(lambda s: s.hostname.lower() == recv[0][1:].lower() or s.sid.lower() == recv[0][1:].lower(), localServer.servers))
                if path:
                    path = path[0].hostname
            else:
                path = path[0].nickname
            target[0].sendraw(304, ':[{}] {}'.format(path, reason))
            timer = threading.Timer(0.01, kill, args=(target[0], quitmsg))
            timer.start()
            return

        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return
        if not self.ocheck('o', 'localkill') and not self.ocheck('o', 'globalkill'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return
        if len(recv) < 2:
            self.sendraw(461, ':KILL Not enough parameters')
            return

        target = list(filter(lambda c: c.nickname.lower() == recv[1].lower() or c.uid.lower() == recv[1].lower(), localServer.users))
        if not target:
            self.sendraw(401, '{} :No such nick'.format(recv[1]))
            return
        if target[0].server != localServer and not self.ocheck('o', 'globalkill'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return
        if len(recv) == 2:
            reason = 'No reason'
        else:
            reason = ' '.join(recv[2:])

        if reason.startswith(':'):
            reason = reason[1:]

        path = self.nickname
        target[0].sendraw(304, ':[{}] {}'.format(path, reason))
        msg = '*** Received kill msg for {} ({}@{}) Path {} ({})'.format(target[0].nickname, target[0].ident, target[0].hostname, path, reason)
        localServer.snotice('k', msg)
        localServer.handle('NOTICE', '{} :*** You are being disconnected from this server: [{}] ({})'.format(target[0].nickname, path, reason))

        quitmsg = '[{}] {} kill by {} ({})'.format(self.server.hostname, 'Local' if target[0].server == localServer else 'Global', self.nickname, reason)
        timer = threading.Timer(0.01, kill, args=(target[0], quitmsg))
        timer.start()
        data = ':{} KILL {} :{}'.format(self.uid, target[0].uid, quitmsg)
        localServer.syncToServers(localServer, self.server, data)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)

def kill(user, killmsg):
    user.quit(killmsg, error=True, kill=True)
