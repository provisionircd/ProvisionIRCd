"""
/version command
"""

import ssl

import ircd
from handle.functions import show_support


@ircd.Modules.command
class Version(ircd.Command):
    def __init__(self):
        self.command = 'version'

    def execute(self, client, recv):
        client.sendraw(351, '{} {} [{}]'.format(self.ircd.version, self.ircd.hostname, self.ircd.hostinfo))
        if client.ssl:
            client.send('NOTICE', ':{}'.format(ssl.OPENSSL_VERSION))

        show_support(client, self.ircd)
