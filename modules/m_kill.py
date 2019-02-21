#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/kill command
"""

import ircd
import os
import sys

from handle.functions import match, _print

@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('localkill|globalkill') ### Either flag will be accepted.
@ircd.Modules.commands('kill', 'avadakedavra')
def kill(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            ### Servers can override kill any time.
            target = list(filter(lambda u: u.nickname.lower() == recv[2].lower() or u.uid.lower() == recv[2].lower(), localServer.users))
            if not target:
                return
            quitmsg = ' '.join(recv[3:])[1:]
            reason = ' '.join(recv[8:])[1:][:-1]
            S = recv[0][1:]
            source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
            if not source:
                return
            source = source[0]
            if type(source).__name__ == 'User':
                sourceID = source.uid
                path = source.nickname
            else:
                sourceID = source.sid
                path = source.hostname
            if target[0].socket:
                target[0].sendraw(304, '{}'.format(':[{}] {}'.format(path, reason)))
            data = ':{} KILL {} :{}'.format(sourceID, target[0].uid, quitmsg)
            localServer.new_sync(localServer, self, data)
            target[0].quit(quitmsg, kill=True)
            return

        target = list(filter(lambda c: c.nickname.lower() == recv[1].lower() or c.uid.lower() == recv[1].lower(), localServer.users))
        if not target:
            return self.sendraw(401, '{} :No such nick'.format(recv[1]))

        if target[0].server != localServer and not self.ocheck('o', 'globalkill'):
            return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')

        if 'except' in localServer.conf and 'kill' in localServer.conf['except'] and type(self).__name__ != 'Server':
            check_host = '{}@{}'.format(target[0].ident, target[0].hostname)
            for e in localServer.conf['except']['kill']:
                if match(e, check_host):
                    localServer.notice(self, '*** User {} matches a kill-except ({}) and cannot be killed'.format(target[0].nickname, e))
                    return

        if len(recv) == 2:
            reason = 'No reason'
        else:
            reason = ' '.join(recv[2:])

        if reason.startswith(':'):
            reason = reason[1:]

        path = self.nickname
        localServer.notice(target[0], '*** You are being disconnected from this server: [{}] ({})'.format(path, reason))
        if target[0].socket:
            target[0].sendraw(304, '{}'.format(':[{}] {}'.format(path, reason)))
        msg = '*** Received kill msg for {} ({}@{}) Path {} ({})'.format(target[0].nickname, target[0].ident, target[0].hostname, path, reason)
        localServer.snotice('k', msg)

        quitmsg = '[{}] {} kill by {} ({})'.format(self.server.hostname, 'Local' if target[0].server == localServer else 'Global', self.nickname, reason)
        data = ':{} KILL {} :{}'.format(self.uid, target[0].uid, quitmsg)
        localServer.new_sync(localServer, self.server, data)
        target[0].quit(quitmsg, kill=True)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
