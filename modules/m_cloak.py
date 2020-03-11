"""
/cloak command
"""

import ircd

from handle.functions import cloak


class Cloak(ircd.Command):
    """
    Converts a host or IP to a cloaked version.
    Syntax: CLOAK <host/IP>
    """
    def __init__(self):
        self.command = 'cloak'
        self.req_modes = 'o'
        self.params = 1

    def execute(self, client, recv):
        self.ircd.notice(client, '* Cloaked version is: {}'.format(cloak(self.ircd, recv[1])))
