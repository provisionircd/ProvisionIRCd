"""
/server and /sid command (server)
"""

import ircd

from handle.functions import logging
from handle.handleLink import syncData, selfIntroduction, validate_server_info

W = '\033[0m'  # white (normal)
R = '\033[31m'  # red
G = '\033[32m'  # green
Y = '\033[33m'  # yellow
B = '\033[34m'  # blue
P = '\033[35m'  # purple


class Server(ircd.Command):
    # Deprecated.
    def __init__(self):
        self.command = 'server'
        self.req_class = 'Server'
        self.params = 4

    def execute(self, client, recv):
        exists = [s for s in self.ircd.servers + [self.ircd] if s.hostname.lower() == recv[2].lower()]
        if exists and client != exists[0]:
            logging.error('Server {} already exists on this network2'.format(recv[2]))
            client.quit('Server already exists on this network')
            return
        if not client.sid:
            logging.error('Direct link with {} denied because their SID is unknown to me'.format(recv[2]))
            client.quit('No SID received')
            return

        # SERVER irc.example.com 1 :versionstring Server name goes here.
        if not client.linkAccept and not client.eos:
            # Information is gathered backwards from recv.
            client.linkAccept = True
            tempName = ' '.join(recv).split(':')[-2]
            client.hostname = tempName.split()[-2].strip()
            client.hopcount = int(tempName.split()[-1])
            client.name = ' '.join(recv[1:]).split(':')[1]  # ' '.join(recv[4:])
            # Snowflake fix.
            if client.hostname not in self.ircd.conf['settings']['ulines']+[self.ircd.conf['settings']['services']]:
                client.name = ' '.join(client.name.split()[1:])
            if client.name.startswith(':'):
                client.name = client.name[1:]

            logging.info('{}Hostname for {} set: {}{}'.format(G, client, client.hostname, W))
            if [s for s in self.ircd.servers + [self.ircd] if s.hostname.lower() == client.hostname.lower() and s != client]:
                logging.error('Server {} already exists on this network'.format(client.hostname))
                error = 'Error connecting to server {}[{}:{}]: server {} already exists on remote network'.format(client.hostname, ip, port, client.hostname)
                client._send(':{} ERROR :{}'.format(self.ircd.sid, error))
                client.quit('server {} already exists on this network'.format(client.hostname))
                return

            logging.info('{}Server name for {} set: {}{}'.format(G, client, client.name, W))
            logging.info('{}Hopcount for {} set: {}{}'.format(G, client, client.hopcount, W))
            logging.info('{}SID for {} set: {}{}'.format(G, client, client.sid, W))

            if validate_server_info(self, client):
                selfIntroduction(self.ircd, client)
                data = ':{} SID {} 1 {} :{}'.format(self.ircd.sid, client.hostname, client.sid, client.name)
                self.ircd.new_sync(self.ircd, client, data)
                for server in [server for server in self.ircd.servers if server.sid and server != client and server.eos]:
                    logging.info('Introducing {} to {}'.format(server.hostname, client.hostname))
                    sid = self.ircd.sid if server.socket else server.uplink.sid
                    data = ':{} SID {} {} {} :{}'.format(sid, server.hostname, int(server.hopcount) + 1, server.sid, server.name)
                    client._send(data)

                if hasattr(client, 'outgoing') and client.outgoing:
                    syncData(self.ircd, client)


@ircd.Modules.command
class Sid(ircd.Command):
    def __init__(self):
        self.command = 'sid'
        self.params = 4
        self.req_class = 'Server'

    def execute(self, client, recv):
        # :420 SID link1.provisionweb.org 1 420 :ProvisionDev
        uplink = [s for s in self.ircd.servers if s.sid == recv[0][1:]]
        if not uplink:
            client._send(':{} ERROR :Could not find uplink for {}'.format(self.ircd.sid, recv[0][1:]))
            client.quit()
            return
        uplink = uplink[0]
        sid = recv[4]
        hostname = recv[2]
        name = ' '.join(recv[5:])[1:]
        hopcount = int(recv[3])
        if client.hostname == hostname:
            logging.debug(f'New incoming link: {hostname}')
            if validate_server_info(self, client):
                client.name = name
                selfIntroduction(self.ircd, client)
                data = ':{} SID {} 1 {} :{}'.format(self.ircd.sid, client.hostname, client.sid, client.name)
                self.ircd.new_sync(self.ircd, client, data)
                for server in [server for server in self.ircd.servers if server.sid and server != client and server.eos]:
                    logging.info('Introducing {} to {}'.format(server.hostname, client.hostname))
                    sid = self.ircd.sid if server.socket else server.uplink.sid
                    data = ':{} SID {} {} {} :{}'.format(sid, server.hostname, int(server.hopcount) + 1, server.sid, server.name)
                    client._send(data)

                    if hasattr(client, 'outgoing') and client.outgoing:
                        syncData(self.ircd, client)
            return

        for server in [server for server in self.ircd.servers if server.sid == sid and server != client]:
            client._send(':{} ERROR :SID {} is already in use on that network'.format(self.ircd.sid, sid))
            client.quit('SID {} is already in use on that network'.format(sid))
            return
        for server in [server for server in self.ircd.servers if server.hostname.lower() == hostname.lower() and server != client]:
            client._send(':{} ERROR :Hostname {} is already in use on that network'.format(self.ircd.sid, hostname))
            client.quit('Server {} is already in use on that network'.format(hostname))
            return

        newServer = ircd.Server(origin=self.ircd, serverLink=True)
        newServer.hostname = hostname
        newServer.hopcount = hopcount
        newServer.name = ' '.join(recv[5:])[1:]
        newServer.introducedBy = client
        newServer.uplink = uplink
        newServer.sid = sid
        logging.info(f'{G}New server added to the network: {newServer.hostname} ({newServer.name}{W})')
        logging.info('{}SID: {}{}'.format(G, newServer.sid, W))
        logging.info('{}Introduced by: {} ({}) {}'.format(G, newServer.introducedBy.hostname, newServer.introducedBy.sid, W))
        logging.info('{}Uplinked to: {} ({}) {}'.format(G, newServer.uplink.hostname, newServer.uplink.sid, W))
        logging.info('{}Hopcount: {}{}'.format(G, newServer.hopcount, W))
        self.ircd.new_sync(self.ircd, client, ' '.join(recv))
