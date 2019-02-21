#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/tkl, /kline, /gline, /zline, /gzline commands (server)
"""

import ircd
import time
import datetime
import os
import sys
from handle.functions import TKL, _print, valid_expire

def makerMask(data):
    ident = data.split('@')[0]
    if ident == '':
        ident = '*'
    try:
        host = data.split('@')[1]
    except:
        host = '*'
    if host == '':
        host = '*'
    result = '{}@{}'.format(ident, host)
    return result

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('tkl')
def tkl(self, localServer, recv, expire=False):
    if recv[2] == '+':
        TKL.add(self, localServer, recv)
        ### TKL add.
    elif recv[2] == '-':
        TKL.remove(self, localServer, recv, expire=expire)

@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('zline|gzline')
@ircd.Modules.commands('zline', 'gzline')
def zline(self, localServer, recv):
    ### /zline +0 nick/ip reason
    type = 'Z' if recv[0].lower() == 'gzline' else 'z'
    if type == 'Z' and not self.ocheck('o', 'gzline'):
        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
    try:

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
                data = '- {} {} {}'.format(type, mask.split('@')[0], mask.split('@')[1])
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

        if len(recv[2].replace('*', '')) <= 5 and ('@' in recv[2] or '*' in recv[2]):
            self.server.broadcast([self], 'NOTICE {} :*** Notice -- IP range is too small'.format(self.nickname))
            return

        if len(recv) == 3:
            reason = 'No reason'
        else:
            reason = ' '.join(recv[3:])

        if '@' not in recv[2]:
            target = list(filter(lambda c: c.nickname.lower() == recv[2].lower(), localServer.users))
            if not target:
                self.sendraw(401, '{} :No such nick'.format(recv[2]))
                return
            mask = '*@{}'.format(target[0].ip)
        elif '.' not in recv[2].split('@')[1] or not recv[2].split('@')[1].replace('.', '').isdigit():
            self.server.broadcast([self], 'NOTICE {} :*** Notice -- Invalid IP: {}'.format(self.nickname, recv[2].split('@')[1]))
            return
        else:
            mask = makerMask(recv[2])
        if mask:
            data = '+ {} {} {} {} {} {} :{}'.format(type, mask.split('@')[0], mask.split('@')[1], self.fullrealhost(), expire, int(time.time()), reason)
            localServer.handle('tkl', data)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)


@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('kline|gline')
@ircd.Modules.commands('kline', 'gline')
def kline(self, localServer, recv):
    ### /kline +0 nick/ip reason
    type = 'G' if recv[0].lower() == 'gline' else 'g'
    if type == 'G' and not self.ocheck('o', 'gline'):
        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
    try:
        if recv[1][0] == '-':
            try:
                mask = recv[1][1:]
            except:
                self.server.broadcast([self], 'NOTICE {} :*** Notice -- Invalid hostname'.format(self.nickname))
                return
            if type not in localServer.tkl or mask not in localServer.tkl[type]:
                self.server.notice(self, '*** Notice -- No such {}:line: {}'.format('G' if type == 'G' else 'K', mask))
                return
            else:
                data = '- {} {} {}'.format(type, mask.split('@')[0], mask.split('@')[1])
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
                expire = int(time.time()) + valid_expire(recv[1].replace('+',''))

        if len(recv[2].replace('*','')) <= 5 and ('@' in recv[2] or '*' in recv[2]):
            self.server.broadcast([self], 'NOTICE {} :*** Notice -- Host range is too small'.format(self.nickname))
            return

        if len(recv) == 3:
            reason = 'No reason'
        else:
            reason = ' '.join(recv[3:])
        if '@' not in recv[2]:
            target = list(filter(lambda c: c.nickname.lower() == recv[2].lower(), localServer.users))
            if not target:
                self.sendraw(401, '{} :No such nick'.format(recv[2]))
                return
            mask = '*@{}'.format(target[0].hostname)
        elif '.' not in recv[2] and '@' not in recv[2]:
            self.server.broadcast([self], 'NOTICE {} :*** Notice -- Invalid host'.format(self.nickname))
            return
        else:
            mask = makerMask(recv[2])
        if mask:
            data = '+ {} {} {} {} {} {} :{}'.format(type, mask.split('@')[0], mask.split('@')[1], self.fullrealhost(), expire, int(time.time()),reason)
            #TKL.add(localServer,data)
            localServer.handle('tkl', data)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
