import os
import sys
import time
import datetime
from handle.functions import match, valid_expire

from cmds import cmd_tkl
TKL = cmd_tkl.TKL()



def cmd_ZLINE(self, localServer, recv, g=False):
    ### /kline +0 nick/ip reason

    try:
        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return
        if g:
            reqflag = 'gzline'
            type = 'Z'
        else:
            reqflag = 'zline'
            type = 'z'

        if not self.ocheck('o', reqflag) and not self.ocheck('o', 'gzline'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return
        if len(recv) < 2:
            self.sendraw(461, ':{}LINE Not enough parameters'.format('Z' if not g else 'GZ'))
            return

        if recv[1][0] == '-':
            try:
                mask = recv[1][1:]
            except:
                self.server.broadcast([self], 'NOTICE {} :*** Notice -- Invalid IP'.format(self.nickname))
                return
            if type not in localServer.tkl or mask not in localServer.tkl[type]:
                self.server.broadcast([self], 'NOTICE {} :*** Notice -- No such Z:Line: {}'.format(self.nickname, mask))
                return
            else:
                data = ':{} - {} {} {}'.format(localServer.sid, type, mask.split('@')[0], mask.split('@')[1])
                #TKL.remove(localServer, data)
                localServer.handle('tkl', data)
                return

        mask = None
        if recv[1][0] != '+' or not valid_expire(recv[1].replace('+', '')):
            self.server.broadcast([self], 'NOTICE {} :*** Notice -- Invalid expire'.format(self.nickname))
            return
        else:
            if recv[1][1:] == '0':
                expire = '0'
            else:
                expire = int(time.time()) + valid_expire(recv[1].replace('+', ''))

        if len(recv[2].replace('*','')) <= 5 and ('@' in recv[2] or '*' in recv[2]):
            self.server.broadcast([self], 'NOTICE {} :*** Notice -- IP range is too small'.format(self.nickname))
            return

        if len(recv) == 3:
            reason = 'No reason'
        else:
            reason = ' '.join(recv[3:])

        #if '@' in recv[2]:
        #    recv[2] = recv[2].split('@')[0]
        if '@' not in recv[2]:
            target = list(filter(lambda c: c.nickname.lower() == recv[2].lower(), localServer.users))
            if not target:
                self.sendraw(401, '{} :No such nick'.format(recv[2]))
                return
            mask = '*@{}'.format(target[0].ip)
        elif '.' not in recv[2].split('@')[1]:
            self.server.broadcast([self], 'NOTICE {} :*** Notice -- Invalid IP: {}'.format(self.nickname, recv[2].split('@')[1]))
            return
        else:
            mask = makerMask(recv[2])
        if mask:
            #data = ':{} TKL + {} * {} {} {} {} :{}'.format(localServer.sid,type,mask,self.nickname,expire,int(time.time()),reason).split()
            data = ':{} + {} {} {} {} {} {} :{}'.format(localServer.sid, type, mask.split('@')[0], mask.split('@')[1], self.fullrealhost(), expire, int(time.time()), reason)
            localServer.handle('tkl', data)
            #TKL.add(localServer,data)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e)