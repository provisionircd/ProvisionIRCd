"""
/motd command
"""

import ircd

from handle.functions import logging

@ircd.Modules.commands('motd')
def motd(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            if len(recv) == 1:
                with open(localServer.confdir+'ircd.motd') as f:
                    b_motd = bytes(f.read(), 'utf-8')
                    logging.debug('Sending to remote: {}'.format(b_motd))
                    self._send('MOTD {}'.format(b_motd))
                    return
            else:
                logging.debug('Received remote motd response.')
                logging.debug('Sending reply to: {}'.format(localServer.remote_motd_request[self]))
                b_motd = ' '.join(recv[1:])
                logging.debug('Bytes: {}'.format(b_motd))
                localServer.remote_motd_request[self].sendraw(375, '{} Message of the Day'.format(self.hostname))
                for line in eval(b_motd).decode('utf-8').split('\n'):
                    localServer.remote_motd_request[self].sendraw(372, ':- {}'.format(line))
                localServer.remote_motd_request[self].sendraw(376, ':End of Message of the Day.')

        else:
            if len(recv) == 1:
                self.sendraw(375, '{} Message of the Day'.format(localServer.hostname))
                with open(localServer.confdir+'ircd.motd') as f:
                    for line in f.read().split('\n'):
                        self.sendraw(372, ':- {}'.format(line))
                    self.sendraw(376, ':End of Message of the Day.')
            else:
                remoteserver = recv[1].lower()
                if hasattr(localServer, 'remote_motd_request') and remoteserver.lower() != localServer.hostname.lower():
                    server_exists = [server for server in localServer.servers if server.hostname.lower() == remoteserver]
                    if not server_exists and remoteserver != localServer.hostname:
                        return self.sendraw(402, '{} :No such server'.format(remoteserver))
                    if not server_exists[0].socket: ### Will fix hops later.
                        return localServer.notice(self, '* You can only request remote MOTDs from directly linked servers.')
                    if 'o' not in self.modes:
                        self.flood_penalty += 50000
                    server = server_exists[0] if server_exists[0].socket else server_exists[0].introducedBy
                    localServer.remote_motd_request[server] = self
                    server._send('MOTD')

    except Exception as ex:
        logging.exception(ex)

def init(self, reload=False):
    self.remote_motd_request = {}
