#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/chghost command
"""

import ircd

from handle.functions import _print
import os
import sys

@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.commands('chgident')
def chgident(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            source = self
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))
            if not self:
                return
            self = self[0]
            recv = recv[1:]
        else:
            source = localServer

        target = list(filter(lambda u: u.nickname == recv[1], localServer.users))
        if not target:
            return self.sendraw(401, '{} :No such nick'.format(recv[1]))
        target = target[0]
        ident = str(recv[2][:12]).strip()
        valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
        for c in str(ident):
            if c.lower() not in valid:
                ident = ident.replace(c, '').rstrip()
        if ident == target.ident or not ident:
            return
        target.setinfo(ident, t='ident', source=source)
        localServer.snotice('s', '*** {} ({}@{}) used CHGIDENT to change the ident of {} to "{}"'.format(self.nickname, self.ident, self.hostname, target.nickname, target.ident))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
