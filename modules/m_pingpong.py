"""
ping/pong handler
"""

import ircd
import time

from handle.handleLink import syncData
from handle.functions import logging


@ircd.Modules.command
class Ping(ircd.Command):
    """
    Ping/pong
    """
    def __init__(self):
        self.command = 'ping'
        self.params = 1


    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            dest = list(filter(lambda s: s.sid == recv[3] or s.hostname == recv[3], self.ircd.servers+[self.ircd]))
            if not dest:
                logging.error('Server {} requested a PING to unknown server {}'.format(client, recv[3]))
                return
            source = list(filter(lambda s: s.sid == recv[2] or s.hostname == recv[2], self.ircd.servers+[self.ircd]))[0]

            if source not in self.ircd.syncDone:
                local_only = False
                if source in self.ircd.sync_queue:
                    local_only = True
                    logging.info('Syncing only local users to {}'.format(source))
                    del self.ircd.sync_queue[source]
                syncData(self.ircd, source, local_only=local_only)
                return

            ### Old: data = ':{} PONG {} {}'.format(dest[0].sid, dest[0].hostname, recv[2])
            if client.eos and (dest[0].eos or dest[0] == self.ircd):
                data = ':{} PONG {} {}'.format(dest[0].sid, dest[0].hostname, recv[2])
                client._send(data)
        else:
            client._send(':{} PONG {} :{}'.format(self.ircd.hostname, self.ircd.hostname, recv[1]))


@ircd.Modules.command
class Pong(ircd.Command):
    """
    Reply to a PING command.
    """
    def __init__(self):
        self.command = 'pong'
        self.params = 1


    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            ### Sent: :00B PONG services.dev.provisionweb.org dev.provisionweb.org
            ### Received: :test.provisionweb.org PONG test.provisionweb.org :services.dev.provisionweb.org
            source = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], self.ircd.servers))[0]
            source.ping = int(time.time())
        client.lag = int((time.time() * 1000) - client.lastPingSent)
