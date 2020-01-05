#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/version command
"""

import ircd

import ssl
from handle.functions import show_support

@ircd.Modules.commands('version')
def version(self, localServer, recv):
    self.sendraw(351, '{} {} [{}]'.format(self.server.version, localServer.hostname, localServer.hostinfo))
    if self.ssl:
        self.send('NOTICE', ':{}'.format(ssl.OPENSSL_VERSION))

    show_support(self, localServer)
