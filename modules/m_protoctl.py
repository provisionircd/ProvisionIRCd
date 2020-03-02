"""
/protoctl command (server)
"""

import ircd

from handle.functions import logging, update_support

W  = '\033[0m'  # white (normal)
P  = '\033[35m' # purple


class Protoctl(ircd.Command):
    def __init__(self):
        self.command = 'protoctl'
        self.req_class = 'Server'


    def execute(self, client, recv):
        if not hasattr(client, 'protoctl'):
            client.protoctl = []
        try:
            for p in [p for p in recv[2:] if p not in client.protoctl]:
                try:
                    cap = p.split('=')[0]
                    param = None
                    client.protoctl.append(cap)
                    if '=' in p:
                        param = p.split('=')[1]
                    if cap == 'EAUTH' and param:
                        client.hostname = param.split(',')[0]
                        logging.info('Hostname set from EAUTH: {}'.format(client.hostname))
                        if [s for s in self.ircd.servers+[self.ircd] if s.hostname.lower() == client.hostname.lower() and s != client]:
                            ip, port = client.socket.getpeername()
                            error = 'Error connecting to server {}[{}:{}]: server already exists on remote network'.format(self.ircd.hostname, ip, port)
                            client._send(':{} ERROR :{}'.format(self.ircd.sid, error))
                            client.quit('server already exist on this network')
                            return

                    elif cap == 'SID' and param:
                        for server in [server for server in self.ircd.servers if server.sid == param and server != client]:
                            client._send(':{} ERROR :SID {} is already in use on that network'.format(self.ircd.sid, param))
                            client.quit('SID {} is already in use on that network'.format(param))
                            return
                        client.sid = param

                    elif cap == 'CHANMODES':
                        remote_modes = param.split(',')
                        local_modes = self.ircd.chmodes_string.split(',')
                        missing_modes = []
                        for n in self.ircd.channel_modes:
                            for m in [m for m in remote_modes[n] if m not in local_modes[n]]:
                                missing_modes.append(m)
                        if missing_modes:
                            # The error is outgoing and will be displayed on the REMOTE server.
                            ip, port = client.socket.getpeername()
                            error = 'Link denied for {}[{}:{}]: they are missing channel modes: {}'.format(
                            client.hostname, ip, port, ', '.join(missing_modes) )

                            client._send(':{} ERROR :{}'.format(self.ircd.sid, error))

                            client.quit('we are missing channel modes: {}'.format(', '.join(missing_modes)))
                            return

                    elif cap == 'EXTBAN':
                        remote_prefix = param[0]
                        remote_ban_types = param.split(',')[1]
                        local_prefix = None
                        if 'EXTBAN' in self.ircd.support:
                            local_prefix = self.ircd.support['EXTBAN'][0]
                        if remote_prefix != local_prefix:
                            ip, port = client.socket.getpeername()
                            error = 'Link denied for {}[{}:{}]: extban prefixes are not the same. We have: {} but they have: {}'.format(
                            client.hostname, ip, port, remote_prefix, local_prefix )

                            client._send(':{} ERROR :extban prefixes are not the same. We have: {} but they have: {}'.format(self.ircd.sid, remote_prefix, local_prefix))
                            client.quit('extban prefixes are not the same. We have: {} but they have: {}'.format(local_prefix, remote_prefix))
                            return
                        local_ban_types = self.ircd.support['EXTBAN'][1:]
                        logging.info('We have bantypes: {}'.format(local_ban_types))
                        missing_ext_types = []
                        for m in [m for m in remote_ban_types if m not in local_ban_types]:
                            missing_ext_types.append(m)
                        if missing_ext_types:
                            error = 'Link denied for {}[{}:{}]: they are missing ext bans: {}'.format(
                            client.hostname, ip, port, ', '.join(missing_ext_types)  )
                            client._send(':{} ERROR :{}'.format(self.ircd.sid, error))
                            client.quit('we are missing ext bans: {}'.format(', '.join(missing_ext_types)))
                            return

                except Exception as ex:
                    logging.exception(ex)
                    client.quit(str(ex))

                logging.info('{}Added PROTOCTL support for {} for server {}{}'.format(P, p, client, W))

        except Exception as ex:
            logging.exception(ex)
