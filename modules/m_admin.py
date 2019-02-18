#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/admin command
"""

import ircd

@ircd.Modules.commands('admin')
def admin(self, localServer, recv):
    localServer.conf['admin']
    self.sendraw(256, ':Administrative info about {}'.format(localServer.hostname))
    for line in localServer.conf['admin']:
        self.sendraw(257, ':{}'.format(line))
