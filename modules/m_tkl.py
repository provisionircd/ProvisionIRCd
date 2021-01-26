"""
/tkl (server), /kline, /gline, /zline, /gzline commands
"""

import time

import ircd
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


class Tkl(ircd.Command):
    def __init__(self):
        self.command = 'tkl'
        self.req_class = 'Server'

    def execute(self, client, recv, expire=False):
        if recv[2] == '+':
            TKL.add(client, self.ircd, recv)
            # TKL add.
        elif recv[2] == '-':
            TKL.remove(client, self.ircd, recv, expire=expire)


class Zline(ircd.Command):
    """
    Bans a user from a server (zline) or entire network (gzline) by IP address.
    -
    Syntax: ZLINE <expire> <nick|ip> <reason>
    Example: ZLINE +1d R00T_UK Be gone.
    This will remove and ban user R00T_UK from the server. Ban will expire in 1 day.
    Banning on nickname only works when the user is currently online.
    -
    Expire formats can be: m (minutes), h (hours), d (days), w (weeks), and M (months, 30 days per unit).
    Stacking (like +1d12h) is not yet supported.
    -
    To remove a global Z:line, use -ip as the parameter.
    Example: GZLINE -*@12.34.56.78
    """

    def __init__(self):
        self.command = ['zline', 'gzline']
        self.req_flags = 'zline|gzline'
        self.params = 1

    def execute(self, client, recv):
        # /zline +0 nick/ip reason
        type = 'Z' if recv[0].lower() == 'gzline' else 'z'
        if type == 'Z' and not client.ocheck('o', 'gzline'):
            return client.sendraw(self.ERR.NOPRIVILEGES, ':Permission denied - You do not have the correct IRC Operator privileges')
        try:

            if recv[1][0] == '-':
                try:
                    mask = recv[1][1:]
                except:
                    return self.ircd.notice(client, '*** Notice -- Invalid IP'.format(client.nickname))
                if not mask:
                    return self.ircd.notice(client, '*** Syntax: /{} -mask'.format(recv[0].upper()))
                if type not in self.ircd.tkl or mask not in self.ircd.tkl[type]:
                    return self.ircd.notice(client, '*** Notice -- No such Z:Line: {}'.format(client.nickname, mask))
                else:
                    data = '- {} {} {}'.format(type, mask.split('@')[0], mask.split('@')[1])
                    self.ircd.handle('tkl', data)
                    return
            else:
                if len(recv) < 3:
                    return client.sendraw(self.ERR.NEEDMOREPARAMS, ':{} Not enough parameters.'.format(recv[0].upper()))
            mask = None
            if recv[1][0] != '+' or not valid_expire(recv[1].replace('+', '')):
                return self.ircd.notice(client, '*** Notice -- Invalid expire'.format(client.nickname))
            else:
                if recv[1][1:] == '0':
                    expire = '0'
                else:
                    expire = int(time.time()) + valid_expire(recv[1].replace('+', ''))

            if len(recv[2].replace('*', '')) <= 5 and ('@' in recv[2] or '*' in recv[2]):
                return self.ircd.notice(client, '*** Notice -- IP range is too small'.format(client.nickname))

            if len(recv) == 3:
                reason = 'No reason'
            else:
                reason = ' '.join(recv[3:])

            if '@' not in recv[2]:
                target = list(filter(lambda c: c.nickname.lower() == recv[2].lower(), self.ircd.users))
                if not target:
                    return client.sendraw(401, '{} :No such nick'.format(recv[2]))
                mask = '*@{}'.format(target[0].ip)
            elif '.' not in recv[2].split('@')[1] or not recv[2].split('@')[1].replace('.', '').isdigit():
                return self.ircd.notice(client, '*** Notice -- Invalid IP: {}'.format(client.nickname, recv[2].split('@')[1]))
            else:
                mask = makerMask(recv[2])
            if mask:
                data = '+ {} {} {} {} {} {} :{}'.format(type, mask.split('@')[0], mask.split('@')[1], client.fullrealhost(), expire, int(time.time()), reason)
                self.ircd.handle('tkl', data)

        except Exception as ex:
            logging.exception(ex)


class Kline(ircd.Command):
    """
    Bans a user from a server (kline) or entire network (gline) by hostname.
    -
    Syntax: KLINE <expire> <nick|host> <reason>
    Example: KLINE +1d Kevin Be gone.
    This will remove and ban user Kevin from the server. Ban will expire in 1 day.
    Banning on nickname only works when the user is currently online.
    -
    Expire formats can be: m (minutes), h (hours), d (days), w (weeks), and M (months, 30 days per unit).
    Stacking (like +1d12h) is not yet supported.
    -
    To remove a global ban, use -host as the parameter.
    Example: GLINE -*@12.34.56.78.prioritytelecom.net
    """

    def __init__(self):
        self.command = ['kline', 'gline']
        self.req_flags = 'kline|gline'
        self.params = 1

    def execute(self, client, recv):
        type = 'G' if recv[0].lower() == 'gline' else 'g'
        if type == 'G' and not client.ocheck('o', 'gline'):
            return client.sendraw(self.ERR.NOPRIVILEGES, ':Permission denied - You do not have the correct IRC Operator privileges')
        try:
            if recv[1][0] == '-':
                try:
                    mask = recv[1][1:]
                except:
                    return client.server.broadcast([client], 'NOTICE {} :*** Notice -- Invalid hostname'.format(client.nickname))
                if type not in self.ircd.tkl or mask not in self.ircd.tkl[type]:
                    return client.server.notice(client, '*** Notice -- No such {}:line: {}'.format('G' if type == 'G' else 'K', mask))
                else:
                    data = '- {} {} {}'.format(type, mask.split('@')[0], mask.split('@')[1])
                    # TKL.remove(self.ircd, data)
                    self.ircd.handle('tkl', data)
                    return
            else:
                if len(recv) < 3:
                    return client.sendraw(self.ERR.NEEDMOREPARAMS, ':{} Not enough parameters.'.format(recv[0].upper()))
            mask = None
            if recv[1][0] != '+' or not valid_expire(recv[1].replace('+', '')):
                client.server.broadcast([client], 'NOTICE {} :*** Notice -- Invalid expire'.format(client.nickname))
                return
            else:
                if recv[1][1:] == '0':
                    expire = '0'
                else:
                    expire = int(time.time()) + valid_expire(recv[1].replace('+', ''))

            if len(recv[2].replace('*', '')) <= 5 and ('@' in recv[2] or '*' in recv[2]):
                client.server.broadcast([client], 'NOTICE {} :*** Notice -- Host range is too small'.format(client.nickname))
                return

            if len(recv) == 3:
                reason = 'No reason'
            else:
                reason = ' '.join(recv[3:])
            if '@' not in recv[2]:
                target = list(filter(lambda c: c.nickname.lower() == recv[2].lower(), self.ircd.users))
                if not target:
                    client.sendraw(401, '{} :No such nick'.format(recv[2]))
                    return
                mask = '*@{}'.format(target[0].hostname)
            elif '.' not in recv[2] and '@' not in recv[2]:
                client.server.broadcast([client], 'NOTICE {} :*** Notice -- Invalid host'.format(client.nickname))
                return
            else:
                mask = makerMask(recv[2])
            if mask:
                data = '+ {} {} {} {} {} {} :{}'.format(type, mask.split('@')[0], mask.split('@')[1], client.fullrealhost(), expire, int(time.time()), reason)
                # TKL.add(self.ircd,data)
                self.ircd.handle('tkl', data)

        except Exception as ex:
            logging.exception(ex)
