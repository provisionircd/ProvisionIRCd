import os
import sys

def cmd_SANICK(self, localServer, recv):
    try:
        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return
        if not self.ocheck('o', 'localsacmds') and not self.ocheck('o', 'globalsacmds'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return
        if len(recv) < 3:
            self.sendraw(461, ':SANICK Not enough parameters')
            return

        target = list(filter(lambda c: c.nickname.lower() == recv[1].lower(), localServer.users))
        if not target:
            self.sendraw(401, '{} :No such nick'.format(recv[1]))
            return

        if target[0].server != localServer and not self.ocheck('o', 'globalsacmds'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return

        if target[0].nickname == recv[2]:
            return

        if 'S' in target[0].modes:
            localServer.handle('NOTICE', '{} :*** You cannot use /SANICK on services.'.format(self.nickname))
            return

        nick = list(filter(lambda u: u.nickname == recv[2], localServer.users))
        if nick:
            localServer.handle('NOTICE', '{} :*** Nickname {} is already in use'.format(self.uid, recv[2]))
            return

        if recv[2][0].isdigit():
            localServer.handle('NOTICE', '{} :*** Nicknames may not start with a number'.format(self.uid))
            return

        snomsg = '*** {} ({}@{}) used SANICK to change nickname {} to {}'.format(self.nickname, self.ident, self.hostname, target[0].nickname, recv[2])
        localServer.snotice('S', snomsg)

        msg = '*** Your nick has been forcefully changed by  {}.'.format(self.nickname)
        self.server.handle('NOTICE','{} :{}'.format(target[0].nickname, msg))

        p = {'sanick': True}
        target[0].handle('nick', recv[2], params=p)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)
