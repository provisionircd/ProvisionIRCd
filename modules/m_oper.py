"""
/oper command
"""

import ircd

import re
try:
    import bcrypt
except ImportError:
    pass
from handle.functions import match, logging


@ircd.Modules.command
class Oper(ircd.Command):
    """Enable IRC operator access.

    Syntax: OPER <username> <password>
    """
    def __init__(self):
        self.command = 'oper'
        self.params = 2


    def execute(self, client, recv):
        if 'o' in client.modes:
            return

        if 'opers' not in self.ircd.conf:
            client.flood_penalty += 350000
            return client.sendraw(491, ':No O:lines for your host')

        if recv[1] not in self.ircd.conf['opers']:
            client.flood_penalty += 350000
            client.sendraw(491, ':No O:lines for your host')
            msg = '*** Failed oper attempt by {} [{}] ({}@{}): username not found'.format(client.nickname, recv[1], client.ident, client.hostname)
            return self.ircd.snotice('o', msg)

        if self.ircd.conf['opers'][recv[1]]['password'].startswith('$2b$') and len(self.ircd.conf['opers'][recv[1]]['password']) > 58:
            logging.debug('Detected bcrypt for /oper')
            password = recv[2].encode('utf-8') ### Bytes password, plain.
            hashed = self.ircd.conf['opers'][recv[1]]['password'].encode('utf-8') ### Bytes password, hashed.
            if not bcrypt.checkpw(password, hashed):
                client.flood_penalty += 350000
                client.sendraw(491, ':No O:lines for your host')
                msg = '*** Failed oper attempt by {} [{}] ({}@{}): incorrect password'.format(client.nickname, recv[1], client.ident, client.hostname)
                return self.ircd.snotice('o', msg)

        elif recv[2] != self.ircd.conf['opers'][recv[1]]['password']:
            client.flood_penalty += 350000
            client.sendraw(491, ':No O:lines for your host')
            msg = '*** Failed oper attempt by {} [{}] ({}@{}): incorrect password'.format(client.nickname, recv[1], client.ident, client.hostname)
            return self.ircd.snotice('o', msg)

        if 'requiremodes' in self.ircd.conf['opers'][recv[1]]:
            for m in str(self.ircd.conf['opers'][recv[1]]['requiremodes']):
                if m not in client.modes and m not in '+-':
                    client.flood_penalty += 350000
                    client.sendraw(491, ':No O:lines for your host')
                    msg = '*** Failed oper attempt by {} [{}] ({}@{}): mode requirement not met'.format(client.nickname, recv[1], client.ident, client.hostname)
                    return self.ircd.snotice('o', msg)

        selfhost = client.fullrealhost().split('!')[1]
        operhost = self.ircd.conf['opers'][recv[1]]['host']
        hostMatch = False
        for host in self.ircd.conf['opers'][recv[1]]['host']:
            if match(host, selfhost):
                hostMatch = True
                break

        if not hostMatch:
            client.flood_penalty += 350000
            client.sendraw(491,':No O:lines for your host')
            msg = '*** Failed oper attempt by {} [{}] ({}@{}): host does not match'.format(client.nickname, recv[1], client.ident,client.hostname)
            return self.ircd.snotice('o', msg)

        operClass = self.ircd.conf['opers'][recv[1]]['class']
        totalClasses = list(filter(lambda u: u.server == client.server and u.cls == operClass, client.server.users))
        if len(totalClasses) >= int(client.server.conf['class'][operClass]['max']):
            client.flood_penalty += 350000
            client.sendraw(491, ':No O:lines for your host')
            msg = '*** Failed oper attempt by {} [{}] ({}@{}): limit reached for their oper class'.format(client.nickname, recv[1], client.ident, client.hostname)
            return self.ircd.snotice('o', msg)
        else:
            client.cls = operClass
            operclass = self.ircd.conf['opers'][recv[1]]['operclass']
            parent = None if 'parent' not in self.ircd.conf['operclass'][operclass] else self.ircd.conf['operclass'][operclass]['parent']
            client.operflags = []
            all_flags = [flag for flag in self.ircd.conf['operclass'][operclass]['flags'] if '|' not in flag]
            if parent:
                all_flags += [flag for flag in self.ircd.conf['operclass'][parent]['flags'] if '|' not in flag]

            for flag in [flag for flag in all_flags if flag.lower() not in client.operflags]:
                client.operflags.append(flag.lower())

            ### Do not automatically set following modes: gqrzH
            modes = 'o'+re.sub('[ogqrzH]', '', self.ircd.conf['opers'][recv[1]]['modes'])
            client.opermodes = ''
            for m in [m for m in modes if m in self.ircd.user_modes]:
                client.opermodes += m

            client.operaccount = recv[1]
            client.operclass = operclass

            if 'swhois' in self.ircd.conf['opers'][recv[1]]:
                client.swhois = []
                client.operswhois = self.ircd.conf['opers'][recv[1]]['swhois']
                if client.operswhois not in client.swhois:
                    client.swhois.append(client.operswhois[:128])

            if 's' in modes:
                snomasks = ''
                client.snomasks = ''
                for snomask in self.ircd.conf['opers'][recv[1]]['snomasks']:
                    if snomask in self.ircd.snomasks and snomask not in client.snomasks:
                        snomasks += snomask
            if 'operhost' in self.ircd.conf['opers'][recv[1]] and '@' not in self.ircd.conf['opers'][recv[1]]['operhost'] and '!' not in self.ircd.conf['opers'][recv[1]]['operhost']:
                client.setinfo(self.ircd.conf['opers'][recv[1]]['operhost'], t='host', source=self.ircd)

            p = {'override': True}
            client.handle('MODE', '{} +{} {}'.format(client.nickname, client.opermodes, '+'+snomasks if snomasks else ''), params=p)
            client.sendraw(381, ':You are now an IRC Operator.')
            client.flood_penalty = 0
            msg = '*** {} ({}@{}) [{}] is now an IRC Operator (+{})'.format(client.nickname, client.ident, client.hostname, client.operaccount, client.opermodes)
            self.ircd.snotice('o', msg)

            data = ':{} MD client {} operaccount :{}'.format(self.ircd.sid, client.uid, client.operaccount)
            self.ircd.new_sync(self.ircd, client.server, data)

            for line in client.swhois:
                data = ':{} SWHOIS {} :{}'.format(self.ircd.sid, client.uid, line)
                self.ircd.new_sync(self.ircd, client.server, data)
