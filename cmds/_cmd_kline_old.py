import os
import sys
import time
import datetime
from handle.functions import match, valid_expire, TKL

def makerMask(data):
    ident = data.split('@')[0]
    if ident == '':ident = '*'
    try:host = data.split('@')[1]
    except:host = '*'
    if host == '':host = '*'
    result = '{}@{}'.format(ident, host)
    return result

def cmd_KLINE(self, localServer, recv, g=False):
    ### /kline +0 nick/ip reason
    print('kerel wat: {}'.format(recv))
    try:
        if 'o' not in self.modes:
            self.sendraw(481,':Permission denied - You are not an IRC Operator')
            return
        if g:
            reqflag = 'gline'
            type = 'G'
        else:
            reqflag = 'kline'
            type = 'g'

        if not self.ocheck('o',reqflag) and not self.ocheck('o','gline'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return
        if len(recv) < 2:
            self.sendraw(461,':{}LINE Not enough parameters'.format('K' if not g else 'G'))
            return

        if recv[1][0] == '-':
            try:
                mask = recv[1][1:]
            except:
                self.server.broadcast([self],'NOTICE {} :*** Notice -- Invalid hostname'.format(self.nickname))
                return
            if type not in localServer.tkl or mask not in localServer.tkl[type]:
                self.server.broadcast([self],'NOTICE {} :*** Notice -- No such kline: {}'.format(self.nickname,mask))
                return
            else:
                data = ':{} TKL - {} {} {}'.format(localServer.sid,type,mask.split('@')[0],mask.split('@')[1]).split()
                TKL.remove(localServer,data)
                return
        mask = None
        if recv[1][0] != '+' or not valid_expire(recv[1].replace('+','')):
            self.server.broadcast([self],'NOTICE {} :*** Notice -- Invalid expire'.format(self.nickname))
            return
        else:
            if recv[1][1:] == '0':
                expire = '0'
            else:
                expire = int(time.time()) + valid_expire(recv[1].replace('+',''))

        if len(recv[2].replace('*','')) <= 5 and ('@' in recv[2] or '*' in recv[2]):
            self.server.broadcast([self],'NOTICE {} :*** Notice -- Host range is too small'.format(self.nickname))
            return

        if len(recv) == 3:
            reason = 'No reason'
        else:
            reason = ' '.join(recv[3:])
        if '@' not in recv[2]:
            target = list(filter(lambda c: c.nickname.lower() == recv[2].lower(), localServer.users))
            if target == []:
                self.sendraw(401,'{} :No such nick'.format(recv[2]))
                return
            mask = '*@{}'.format(target[0].hostname)
        elif '.' not in recv[2] and '@' not in recv[2]:
            self.server.broadcast([self],'NOTICE {} :*** Notice -- Invalid host'.format(self.nickname))
            return
        else:
            mask = makerMask(recv[2])
        if mask:
            print('eh?')
            data = ':{} + {} {} {} {} {} {} :{}'.format(localServer.sid,type,mask.split('@')[0],mask.split('@')[1],self.fullrealhost(),expire,int(time.time()),reason)
            #TKL.add(localServer,data)
            localServer.handle('tkl', data)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        #print(e)