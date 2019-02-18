import os
import sys

def cmd_SAJOIN(self, localServer, recv):
    try:
        if 'o' not in self.modes.lower():
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return
        if not self.ocheck('o','localsacmds') and not self.ocheck('o','globalsacmds'):
            self.sendraw(481,':Permission denied - You do not have the correct IRC Operator privileges')
            return
        if len(recv) < 3:
            self.sendraw(461,':SAJOIN Not enough parameters')
            return

        target = list(filter(lambda c: c.nickname.lower() == recv[1].lower(), localServer.users))
        if not target:
            self.sendraw(401,'{} :No such nick'.format(recv[1]))
            return
        if target[0].server != localServer and not self.ocheck('o','globalsacmds'):
            self.sendraw(481,':Permission denied - You do not have the correct IRC Operator privileges')
            return

        if 'S' in target[0].modes:
            localServer.handle('NOTICE','{} :*** You cannot use /SAJOIN on services.'.format(self.nickname))
            return

        channel = list(filter(lambda c: c.name.lower() == recv[2].lower(), localServer.channels))
        if not channel:
            self.sendraw(401,'{} :No such channel'.format(recv[2]))
            return

        channel = list(filter(lambda c: c.name.lower() == recv[2].lower(), target[0].channels))
        if channel:
            return self.sendraw(443,'{} {} :is already on that channel'.format(target[0].nickname, channel[0].name))

        p = {'sajoin': True}
        target[0].handle('join', recv[2], params=p)

        chan = list(filter(lambda c: c.name.lower() == recv[2].lower(), target[0].channels))
        snomsg = '*** {} ({}@{}) used SAJOIN to make {} join {}'.format(self.nickname, self.ident, self.hostname, target[0].nickname, chan[0].name)
        localServer.snotice('S', snomsg)

        msg = '*** Your were forced to join {}.'.format(recv[2])
        localServer.handle('NOTICE','{} :{}'.format(target[0].nickname,msg))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        if not localServer.forked:
            print(e)