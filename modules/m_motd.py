"""
/motd command
"""

import ircd

from handle.functions import logging


class Motd(ircd.Command):
    """
    Displays the Message of the Day.
    """

    def __init__(self):
        self.command = 'motd'

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            if len(recv) == 1:
                with open(self.ircd.confdir + 'ircd.motd') as f:
                    b_motd = bytes(f.read(), 'utf-8')
                    logging.debug('Sending to remote: {}'.format(b_motd))
                    client._send('MOTD {}'.format(b_motd))
                    return
            else:
                logging.debug('Received remote motd response.')
                logging.debug('Sending reply to: {}'.format(self.ircd.remote_motd_request[client]))
                b_motd = ' '.join(recv[1:])
                logging.debug('Bytes: {}'.format(b_motd))
                self.ircd.remote_motd_request[client].sendraw(self.RPL.ENDOFMOTD, '{} Message of the Day'.format(client.hostname))
                for line in eval(b_motd).decode('utf-8').split('\n'):
                    self.ircd.remote_motd_request[client].sendraw(self.RPL.MOTD, ':- {}'.format(line))
                self.ircd.remote_motd_request[client].sendraw(self.RPL.ENDOFMOTD, ':End of Message of the Day.')

        else:
            if len(recv) == 1:
                client.sendraw(self.RPL.MOTDSTART, '{} Message of the Day'.format(self.ircd.hostname))
                with open(self.ircd.confdir + 'ircd.motd') as f:
                    for line in f.read().split('\n'):
                        client.sendraw(self.RPL.MOTD, ':- {}'.format(line))
                    client.sendraw(self.RPL.ENDOFMOTD, ':End of Message of the Day.')
            else:
                remoteserver = recv[1].lower()
                if hasattr(self.ircd, 'remote_motd_request') and remoteserver.lower() != self.ircd.hostname.lower():
                    server_exists = [server for server in self.ircd.servers if server.hostname.lower() == remoteserver]
                    if not server_exists and remoteserver != self.ircd.hostname:
                        return client.sendraw(402, '{} :No such server'.format(remoteserver))
                    if not server_exists[0].socket:  ### Will fix hops later.
                        return self.ircd.notice(client, '* You can only request remote MOTDs from directly linked servers.')
                    if 'o' not in client.modes:
                        client.flood_penalty += 50000
                    server = server_exists[0] if server_exists[0].socket else server_exists[0].introducedBy
                    self.ircd.remote_motd_request[server] = client
                    server._send('MOTD')


def init(ircd, reload=False):
    ircd.remote_motd_request = {}
