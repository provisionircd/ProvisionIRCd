#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/cloak command
"""

import ircd

from handle.functions import cloak

@ircd.Modules.params(1)
@ircd.Modules.req_modes('o')
@ircd.Modules.commands('cloak')
def cmdcloak(self, localServer, recv):
    localServer.notice(self, '* Cloaked version is: {}'.format(cloak(localServer, recv[1])))
