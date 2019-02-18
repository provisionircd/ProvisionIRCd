#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/sethost command
"""

import ircd
import sys
import os

@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.commands('sethost')
def sethost(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            source = self
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))
            if not self:
                return
            self = self[0]
            recv = recv[1:]
            host = str(recv[1]).strip()
            self.setinfo(host, t='host', source=source)
            return
        else:
            source = self.server

        host = str(recv[1][:64]).strip()
        valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
        for c in str(host):
            if c.lower() not in valid:
                host = host.replace(c, '')
        if host and host != self.cloakhost:
            self.setinfo(host, t='host', source=source)
            localServer.notice(self, '*** Your hostname is now "{}"'.format(self.cloakhost))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
