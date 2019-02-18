import bcrypt
import threading

def cmd_MKPASSWD(self, localServer, recv):
    ### Make this threaded.
    if 'o' not in self.modes:
        self.sendraw(481, ':Permission denied - You are not an IRC Operator')
        return

    if len(recv) < 2:
        localServer.handle('NOTICE', '{} :*** /MKPASSWD <password>'.format(self.nickname))
        return

    if len(recv[1]) == 1:
        localServer.handle('NOTICE', '{} :*** Really? You think that is secure?'.format(self.nickname))
        return

    if len(recv[1]) < 8:
        localServer.handle('NOTICE', '{} :*** Given password is too short.'.format(self.nickname))
        return

    hashed = bcrypt.hashpw(recv[1].encode('utf-8'),bcrypt.gensalt(10)).decode('utf-8')
    localServer.notice(self, '*** Hashed ({}): {}'.format(recv[1], hashed))
