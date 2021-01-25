"""
/eos command (server)
"""

import ircd

from handle.functions import logging

W = '\033[0m'  # white (normal)
Y = '\033[33m'  # yellow


@ircd.Modules.command
class Eos(ircd.Command):
    def __init__(self):
        self.command = 'eos'
        self.req_class = 'Server'

    def execute(self, client, recv):
        source = list(filter(lambda s: s.sid == recv[0][1:], self.ircd.servers))
        if not source:
            logging.error('ERROR: could not find server for {}'.format(recv[0][1:]))
            return
        source = source[0]
        if source.eos:
            logging.error('ERROR: remote server sent EOS twice!', server=self.ircd)
            return
        self.ircd.new_sync(self.ircd, client, ' '.join(recv))
        for server in [server for server in self.ircd.servers if server.eos]:
            data = ':{} PONG {} {}'.format(source.sid, source.hostname, server.hostname)
            server._send(data)
            data = ':{} PONG {} {}'.format(server.sid, server.hostname, source.hostname)
            source._send(data)
        logging.info('{}EOS received by: {}{}'.format(Y, source.hostname, W))

        if source.socket:
            for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'server_link']:
                try:
                    callable[2](client, self.ircd, source)
                except Exception as ex:
                    logging.exception(ex)

        for s in [s for s in self.ircd.servers if s.introducedBy == source]:
            logging.info('Also setting EOS for {} to be true'.format(s))
            s.eos = True
        if source.hostname.lower() in self.ircd.pendingLinks:
            self.ircd.pendingLinks.remove(source.hostname.lower())
        source.eos = True
        if source in self.ircd.sync_queue:
            for e in self.ircd.sync_queue[source]:
                logging.info('Sending queued data to {}: {}'.format(source, e))
                source._send(e)
