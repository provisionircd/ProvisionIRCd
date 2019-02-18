#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
virtual server support
"""

import ircd

@ircd.Modules.params(1)
@ircd.Modules.commands('cserver')
def cserver(self, localServer, recv):
    if self.registered:
        return

@ircd.Modules.params(1)
@ircd.Modules.commands('cpass')
def cpass(self, localServer, recv):
    if self.registered:
        return
