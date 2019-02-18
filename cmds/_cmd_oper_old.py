#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import sys
import bcrypt
from handle.functions import match

def cmd_OPER(self, localServer, recv):
    try:
        if len(recv) < 3:
            self.sendraw(461, ':OPER Not enough parameters')
            return
        if 'o' in self.modes:
            return
        if 'opers' not in localServer.conf:
            self.flood_penalty += 250001
            self.sendraw(491, ':No O:lines for your host')
            return
        if recv[1] not in localServer.conf['opers']:
            self.flood_penalty += 250001
            self.sendraw(491, ':No O:lines for your host')
            msg = '*** Failed oper attempt by {} [{}] ({}@{}): username not found'.format(self.nickname, recv[1], self.ident, self.hostname)
            localServer.snotice('o', msg)
            return

        hashed = localServer.conf['opers'][recv[1]]['password'].encode('utf-8') ### Bytes password, hashed.
        password = recv[2].encode('utf-8') ### Bytes password, plain.
        if not bcrypt.checkpw(password, hashed):
            self.flood_penalty += 250001
            self.sendraw(491, ':No O:lines for your host')
            msg = '*** Failed oper attempt by {} [{}] ({}@{}): incorrect password'.format(self.nickname, recv[1], self.ident, self.hostname)
            localServer.snotice('o', msg)
            return

        if 'requiremodes' in localServer.conf['opers'][recv[1]]:
            for m in str(localServer.conf['opers'][recv[1]]['requiremodes']):
                if m not in self.modes and m not in '+-':
                    self.flood_penalty += 250001
                    self.sendraw(491,':No O:lines for your host')
                    msg = '*** Failed oper attempt by {} [{}] ({}@{}): mode requirement not met'.format(self.nickname, recv[1], self.ident, self.hostname)
                    localServer.snotice('o', msg)
                    return
        selfhost = self.fullrealhost().split('!')[1]
        operhost = localServer.conf['opers'][recv[1]]['host']
        hostMatch = False
        for host in localServer.conf['opers'][recv[1]]['host']:
            if match(host, selfhost):
                hostMatch = True
                break

        if not hostMatch:
            self.flood_penalty += 250001
            self.sendraw(491,':No O:lines for your host')
            msg = '*** Failed oper attempt by {} [{}] ({}@{}): host does not match'.format(self.nickname, recv[1], self.ident,self.hostname)
            localServer.snotice('o', msg)
            return

        operClass = localServer.conf['opers'][recv[1]]['class']
        totalClasses = list(filter(lambda u: u.server == self.server and u.cls == operClass, self.server.users))
        if len(totalClasses) > int(self.server.conf['class'][operClass]['max']):
            self.flood_penalty += 250001
            self.sendraw(491, ':No O:lines for your host')
            msg = '*** Failed oper attempt by {} [{}] ({}@{}): limit reached for their oper class'.format(self.nickname, recv[1], self.ident, self.hostname)
            localServer.snotice('o', msg)
            return
        else:
            self.cls = operClass
            ### Inherit parent flags first.
            try:
                operclass = localServer.conf['opers'][recv[1]]['operclass']
            except KeyError as ex:
                self._send(':{} NOTICE {} :*** Oper error: Missing conf value {}'.format(localServer.hostname, self.uid, ex))
                return
            parent = None if 'parent' not in localServer.conf['operclass'][operclass] else localServer.conf['operclass'][operclass]['parent']
            try:
                if parent:
                    for flag in localServer.conf['operclass'][parent]['flags']:
                        if flag.lower() not in self.operflags:
                            self.operflags.append(flag.lower())

                for flag in localServer.conf['operclass'][operclass]['flags']:
                    if flag.lower() not in self.operflags:
                        self.operflags.append(flag.lower())
            except KeyError as ex:
                self._send(':{} NOTICE {} :*** Oper error: Missing conf value {} (make sure to include operclass.conf)'.format(localServer.hostname, self.uid, ex))
                return
            except Exception as ex:
                self._send(':{} NOTICE {} :*** Oper error: {}'.format(localServer.hostname, self.uid, ex))
                return

            ### Do not automatically set following modes: qrzHW
            modes = 'o'+re.sub('[oqrzHW]', '', localServer.conf['opers'][recv[1]]['modes'])
            for m in modes:
                if m not in self.opermodes and m in localServer.umodes:
                    self.opermodes += m

            self.oper = True
            self.operaccount = recv[1]

            if 'swhois' in localServer.conf['opers'][recv[1]]:
                self.operswhois = localServer.conf['opers'][recv[1]]['swhois']
                if self.operswhois not in self.swhois:
                    self.swhois.append(self.operswhois)

            if self.operflags:
                data = ':{} BB {}'.format(self.uid, self.operflags)
                localServer.syncToServers(localServer, self.server, data)

            if 's' in modes:
                snomasks = ''
                for snomask in localServer.conf['opers'][recv[1]]['snomasks']:
                    if snomask in localServer.snomasks and snomask not in self.snomasks:
                        snomasks += snomask
            try:
                self.cloakhost = localServer.conf['opers'][recv[1]]['operhost']
                localServer.syncToServers(localServer, self.server, ':{} SETHOST {}'.format(self.uid, self.cloakhost))
            except:
                pass
            self.handle('MODE', '{} +{} {}'.format(self.nickname, modes, '+'+snomasks if snomasks else ''))
            self.sendraw(381, ':You are now an IRC Operator.')
            self.flood_penalty = 0
            msg = '*** {} ({}@{}) [{}] is now an IRC Operator (+{})'.format(self.nickname, self.ident, self.hostname, self.operaccount, self.opermodes)
            localServer.snotice('o', msg)

            data = ':{} MD client {} operaccount :{}'.format(localServer.sid, self.uid, self.operaccount)
            localServer.syncToServers(localServer, self.server, data)

            for line in self.swhois:
                data = ':{} SWHOIS {} :{}'.format(localServer.sid, self.uid, line)
                localServer.syncToServers(localServer, self.server, data)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)