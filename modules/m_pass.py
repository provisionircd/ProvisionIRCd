"""
/pass command (server)
"""

import ircd

from handle.functions import logging
from handle.handleLink import validate_server_info


class Pass(ircd.Command):
    """
    Used by clients to authenticate during connection process.
    """

    def __init__(self):
        self.command = 'pass'
        self.params = 1

    def execute(self, client, recv):
        source = recv[0][1:]
        if type(client).__name__ == 'User':
            if client.registered:
                return client.sendraw(462, ':You may not reregister')
            # Check for server password.
            if client.cls and 'password' in self.ircd.conf['allow'][client.cls]:
                if recv[1] == self.ircd.conf['allow'][client.cls]['password']:
                    client.server_pass_accepted = 1
                    logging.info('Server password accepted for {}'.format(client))
                    return
                else:
                    return client.quit('Invalid password')

        if type(client).__name__ == 'Server' and 'link' not in self.ircd.conf:
            return client.quit('Target has no links configured')

        if len(recv) < 3:
            return
        client.linkpass = recv[2][1:]
        logging.info('Password for {} set: {}'.format(client, client.linkpass))
        ip, port = client.socket.getpeername()
        ip2, port2 = client.socket.getsockname()

        if client.hostname:
            validate_server_info(self, client)
