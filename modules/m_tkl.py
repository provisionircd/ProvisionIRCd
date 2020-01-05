"""
/tkl, /kline, /gline, /zline, /gzline commands (server)
"""

import ircd
import time
import datetime
from handle.functions import TKL, logging, valid_expire

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

@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('zline|gzline')
@ircd.Modules.commands('zline', 'gzline')
def zline(self, localServer, recv):
    ### /zline +0 nick/ip reason
    """Bans a user from a server (zline) or network (gzline) by IP address.
-
Syntax: /ZLINE <expire> <nick|host> <reason>
Example: /ZLINE +1d Kevin Be gone.
This will remove and ban user Kevin from the server. Ban will expire in 1 day. Banning on nickname only works when the user is currently online.
-
Expire formats can be: m (minutes), h (hours), d (days), w (weeks), and M (months, 30 days).
Stacking, like +1d12h is not yet supported.
-
To remove a ban, use -host as the parameter.
Example: /ZLINE -*@12.34.56.78"""

    type = 'Z' if recv[0].lower() == 'gzline' else 'z'
    if type == 'Z' and not self.ocheck('o', 'gzline'):
        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
    try:

        if recv[1][0] == '-':
            try:
                mask = recv[1][1:]
            except:
                return localServer.notice(self, '*** Notice -- Invalid IP'.format(self.nickname))
            if not mask:
                return localServer.notice(self, '*** Syntax: /{} -mask'.format(recv[0].upper()))
            if type not in localServer.tkl or mask not in localServer.tkl[type]:
                return localServer.notice(self, '*** Notice -- No such Z:Line: {}'.format(self.nickname, mask))
            else:
                data = '- {} {} {}'.format(type, mask.split('@')[0], mask.split('@')[1])
                localServer.handle('tkl', data)
                return
        else:
            if len(recv) < 3:
                return self.sendraw(461, ':{} Not enough parameters.'.format(recv[0].upper()))
        mask = None
        if recv[1][0] != '+' or not valid_expire(recv[1].replace('+', '')):
            return localServer.notice(self, '*** Notice -- Invalid expire'.format(self.nickname))
        else:
            if recv[1][1:] == '0':
                expire = '0'
            else:
                expire = int(time.time()) + valid_expire(recv[1].replace('+', ''))

        if len(recv[2].replace('*', '')) <= 5 and ('@' in recv[2] or '*' in recv[2]):
            return localServer.notice(self, '*** Notice -- IP range is too small'.format(self.nickname))

        if len(recv) == 3:
            reason = 'No reason'
        else:
            reason = ' '.join(recv[3:])

        if '@' not in recv[2]:
            target = list(filter(lambda c: c.nickname.lower() == recv[2].lower(), localServer.users))
            if not target:
                return self.sendraw(401, '{} :No such nick'.format(recv[2]))
            mask = '*@{}'.format(target[0].ip)
        elif '.' not in recv[2].split('@')[1] or not recv[2].split('@')[1].replace('.', '').isdigit():
            return localServer.notice(self, '*** Notice -- Invalid IP: {}'.format(self.nickname, recv[2].split('@')[1]))
        else:
            mask = makerMask(recv[2])
        if mask:
            data = '+ {} {} {} {} {} {} :{}'.format(type, mask.split('@')[0], mask.split('@')[1], self.fullrealhost(), expire, int(time.time()), reason)
            localServer.handle('tkl', data)

    except Exception as ex:
        logging.exception(ex)


@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('kline|gline')
@ircd.Modules.commands('kline', 'gline')
def kline(self, localServer, recv):
    ### /kline +0 nick/ip reason
    """Bans a user from a server (kline) or network (gline) by IP hostname.
-
Syntax: /KLINE <expire> <nick|host> <reason>
Example: /KLINE +1d Kevin Be gone.
This will remove and ban user Kevin from the server. Ban will expire in 1 day. Banning on nickname only works when the user is currently online.
-
Expire formats can be: m (minutes), h (hours), d (days), w (weeks), and M (months, 30 days).
Stacking, like +1d12h is not yet supported.
-
To remove a ban, use -host as the parameter.
Example: /ZLINE -*@12.34.56.78.prioritytelecom.net"""
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
        else:
            if len(recv) < 3:
                return self.sendraw(461, ':{} Not enough parameters.'.format(recv[0].upper()))
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
        logging.exception(ex)
