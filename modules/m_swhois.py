#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/swhois command (server)
"""

import ircd
import os
import sys

from handle.functions import _print

@ircd.Modules.params(2)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('swhois')
def swhois(self, localServer, recv):
    try:
        ### :source SWHOIS target :line
        ### :source SWHOIS target :
        user = list(filter(lambda u: u.uid == recv[2] or u.nickname == recv[2], localServer.users))
        if not user:
            return
        user = user[0]
        swhois = ' '.join(recv[3:])[1:] if recv[3].startswith(':') else ' '.join(recv[3:])
        if swhois:
            if swhois not in user.swhois:
                user.swhois.append(swhois)
        else:
            user.swhois = []

        localServer.new_sync(localServer, self, ' '.join(recv))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
