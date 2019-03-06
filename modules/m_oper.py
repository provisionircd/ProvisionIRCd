#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/oper command
"""

import ircd

import re
import bcrypt
from handle.functions import match

@ircd.Modules.params(2)
@ircd.Modules.commands('oper')
def oper(self, localServer, recv):
    if 'o' in self.modes:
        return

    if 'opers' not in localServer.conf:
        self.flood_penalty += 350000
        return self.sendraw(491, ':No O:lines for your host')

    if recv[1] not in localServer.conf['opers']:
        self.flood_penalty += 350000
        self.sendraw(491, ':No O:lines for your host')
        msg = '*** Failed oper attempt by {} [{}] ({}@{}): username not found'.format(self.nickname, recv[1], self.ident, self.hostname)
        return localServer.snotice('o', msg)

    hashed = localServer.conf['opers'][recv[1]]['password'].encode('utf-8') ### Bytes password, hashed.
    password = recv[2].encode('utf-8') ### Bytes password, plain.
    if not bcrypt.checkpw(password, hashed):
        self.flood_penalty += 350000
        self.sendraw(491, ':No O:lines for your host')
        msg = '*** Failed oper attempt by {} [{}] ({}@{}): incorrect password'.format(self.nickname, recv[1], self.ident, self.hostname)
        return localServer.snotice('o', msg)

    if 'requiremodes' in localServer.conf['opers'][recv[1]]:
        for m in str(localServer.conf['opers'][recv[1]]['requiremodes']):
            if m not in self.modes and m not in '+-':
                self.flood_penalty += 350000
                self.sendraw(491, ':No O:lines for your host')
                msg = '*** Failed oper attempt by {} [{}] ({}@{}): mode requirement not met'.format(self.nickname, recv[1], self.ident, self.hostname)
                return localServer.snotice('o', msg)

    selfhost = self.fullrealhost().split('!')[1]
    operhost = localServer.conf['opers'][recv[1]]['host']
    hostMatch = False
    for host in localServer.conf['opers'][recv[1]]['host']:
        if match(host, selfhost):
            hostMatch = True
            break

    if not hostMatch:
        self.flood_penalty += 350000
        self.sendraw(491,':No O:lines for your host')
        msg = '*** Failed oper attempt by {} [{}] ({}@{}): host does not match'.format(self.nickname, recv[1], self.ident,self.hostname)
        return localServer.snotice('o', msg)

    operClass = localServer.conf['opers'][recv[1]]['class']
    totalClasses = list(filter(lambda u: u.server == self.server and u.cls == operClass, self.server.users))
    if len(totalClasses) > int(self.server.conf['class'][operClass]['max']):
        self.flood_penalty += 350000
        self.sendraw(491, ':No O:lines for your host')
        msg = '*** Failed oper attempt by {} [{}] ({}@{}): limit reached for their oper class'.format(self.nickname, recv[1], self.ident, self.hostname)
        return localServer.snotice('o', msg)
    else:
        self.cls = operClass
        operclass = localServer.conf['opers'][recv[1]]['operclass']
        parent = None if 'parent' not in localServer.conf['operclass'][operclass] else localServer.conf['operclass'][operclass]['parent']
        self.operflags = []
        all_flags = [flag for flag in localServer.conf['operclass'][operclass]['flags'] if '|' not in flag]
        if parent:
            all_flags += [flag for flag in localServer.conf['operclass'][parent]['flags'] if '|' not in flag]

        for flag in [flag for flag in all_flags if flag.lower() not in self.operflags]:
            self.operflags.append(flag.lower())

        ### Do not automatically set following modes: qrzHW
        modes = 'o'+re.sub('[oqrzHW]', '', localServer.conf['opers'][recv[1]]['modes'])
        self.opermodes = ''
        for m in [m for m in modes if m in localServer.user_modes]:
            self.opermodes += m

        self.operaccount = recv[1]
        self.operclass = operclass

        if 'swhois' in localServer.conf['opers'][recv[1]]:
            self.swhois = []
            self.operswhois = localServer.conf['opers'][recv[1]]['swhois']
            if self.operswhois not in self.swhois:
                self.swhois.append(self.operswhois[:128])

        if 's' in modes:
            snomasks = ''
            self.snomasks = ''
            for snomask in localServer.conf['opers'][recv[1]]['snomasks']:
                if snomask in localServer.snomasks and snomask not in self.snomasks:
                    snomasks += snomask
        if 'operhost' in localServer.conf['opers'][recv[1]] and '@' not in localServer.conf['opers'][recv[1]]['operhost'] and '!' not in localServer.conf['opers'][recv[1]]['operhost']:
            self.setinfo(localServer.conf['opers'][recv[1]]['operhost'], t='host', source=localServer)

        p = {'override': True}
        self.handle('MODE', '{} +{} {}'.format(self.nickname, self.opermodes, '+'+snomasks if snomasks else ''), params=p)
        self.sendraw(381, ':You are now an IRC Operator.')
        self.flood_penalty = 0
        msg = '*** {} ({}@{}) [{}] is now an IRC Operator (+{})'.format(self.nickname, self.ident, self.hostname, self.operaccount, self.opermodes)
        localServer.snotice('o', msg)

        data = ':{} MD client {} operaccount :{}'.format(localServer.sid, self.uid, self.operaccount)
        localServer.new_sync(localServer, self.server, data)

        for line in self.swhois:
            data = ':{} SWHOIS {} :{}'.format(localServer.sid, self.uid, line)
            localServer.new_sync(localServer, self.server, data)
