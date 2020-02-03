"""
/sqline command (server)
"""

import ircd
import time

from handle.functions import TKL


@ircd.Modules.command
class Sqline(ircd.Command):
    def __init__(self):
        self.command = 'sqline'
        self.req_class = 'Server'
        self.params = 3

    def execute(self, client, recv):
        nick = recv[2]
        reason = ' '.join(recv[3:])

        if reason.startswith(':'):
            reason = reason[1:]

        data = '+ Q * {} {} 0 {} :{}'.format(nick, client.hostname, int(time.time()), reason)
        client.handle('tkl', data)


@ircd.Modules.command
class Unsqline(ircd.Command):
    def __init__(self):
        self.command = 'unsqline'
        self.req_class = 'Server'
        self.params = 3

    def execute(self, client, recv):
        nick = recv[2]
        data = '- Q * {}'.format(nick)
        client.handle('tkl', data)
