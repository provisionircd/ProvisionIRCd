"""
/eos command (server)
"""

import ircd

from handle.functions import logging
from handle.handleLink import syncData

W  = '\033[0m'  # white (normal)
Y  = '\033[33m' # yellow

@ircd.Modules.req_class('Server')
@ircd.Modules.commands('eos')
def eos(self, localServer, recv):
    try:
        source = list(filter(lambda s: s.sid == recv[0][1:], localServer.servers))
        if not source:
            logging.error('ERROR: could not find server for {}'.format(recv[0][1:]))
            return
        source = source[0]
        if source.eos:
            logging.error('ERROR: remote server sent EOS twice!', server=localServer)
            return
        localServer.new_sync(localServer, self, ' '.join(recv))
        for server in [server for server in localServer.servers if server.eos]:
            data = ':{} PONG {} {}'.format(source.sid, source.hostname, server.hostname)
            server._send(data)
            data = ':{} PONG {} {}'.format(server.sid, server.hostname, source.hostname)
            source._send(data)
        logging.info('{}EOS received by: {}{}'.format(Y, source.hostname, W))
        for s in [s for s in localServer.servers if s.introducedBy == source]:
            logging.info('Also setting EOS for {} to be true'.format(s))
            s.eos = True
        if source.hostname.lower() in localServer.pendingLinks:
            localServer.pendingLinks.remove(source.hostname.lower())
        source.eos = True
        if source in localServer.sync_queue:
            for e in localServer.sync_queue[source]:
                logging.info('Sending queued data to {}: {}'.format(source, e))
                source._send(e)

    except Exception as ex:
        logging.exception(ex)
