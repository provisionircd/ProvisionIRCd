"""
/server and /sid command (server)
"""

import ircd
Server = ircd.Server

from handle.functions import match, logging
from handle.handleLink import syncData, selfIntroduction

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
G = '\033[32m' # green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple


class Server(ircd.Command):
    def __init__(self):
        self.command = 'server'
        self.req_class = 'Server'
        self.params = 4


    def execute(self, client, recv):
        exists = [s for s in self.ircd.servers+[self.ircd] if s.hostname.lower() == recv[2].lower()]
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
            client.name = ' '.join(recv[1:]).split(':')[1] # ' '.join(recv[4:])
            client.rawname = ' '.join(recv[3:])
            if client.name.startswith(':'):
                client.name = client.name[1:]

            logging.info('{}Hostname for {} set: {}{}'.format(G, client, client.hostname, W))
            if [s for s in self.ircd.servers+[self.ircd] if s.hostname.lower() == client.hostname.lower() and s != client]:
                logging.error('Server {} already exists on this network'.format(client.hostname))
                error = 'Error connecting to server {}[{}:{}]: server {} already exists on remote network'.format(client.hostname, ip, port, client.hostname)
                client._send(':{} ERROR :{}'.format(self.ircd.sid, error))
                client.quit('server {} already exists on this network'.format(client.hostname))
                return

            logging.info('{}Server name for {} set: {}{}'.format(G, client, client.name, W))
            logging.info('{}Hopcount for {} set: {}{}'.format(G, client, client.hopcount, W))
            logging.info('{}SID for {} set: {}{}'.format(G, client, client.sid, W))

            ip, port = client.socket.getpeername()
            ip2, port2 = client.socket.getsockname()
            if client.hostname not in self.ircd.conf['link']:
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(self.ircd.hostname, ip2, port2)
                client._send(':{} ERROR :{}'.format(self.ircd.sid, error))
                client.quit('no matching link configuration')
                return

            client.cls = self.ircd.conf['link'][client.hostname]['class']
            logging.info('{}Class: {}{}'.format(G, client.cls, W))
            if not client.cls:
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(self.ircd.hostname, ip2, port2)
                client._send(':{} ERROR :{}'.format(self.ircd.sid, error))
                client.quit('no matching link configuration')
                return
            totalClasses = list(filter(lambda s: s.cls == client.cls, self.ircd.servers))
            if len(totalClasses) > int(self.ircd.conf['class'][client.cls]['max']):
                client.quit('Maximum server connections for this class reached')
                return

            if client.linkpass:
                if client.linkpass != self.ircd.conf['link'][client.hostname]['pass']:
                    error = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(self.ircd.hostname, ip2, port2)
                    client._send(':{} ERROR :{}'.format(self.ircd.sid, error))
                    client.quit('no matching link configuration')
                    return

            if not match(self.ircd.conf['link'][client.hostname]['incoming']['host'], ip):
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(self.ircd.hostname, ip2, port2)
                client._send(':{} ERROR :{}'.format(self.ircd.sid, error))
                client.quit('no matching link configuration')
                return

            if client.hostname not in self.ircd.conf['settings']['ulines']:
                for cap in [cap.split('=')[0] for cap in self.ircd.server_support]:
                    if cap in client.protoctl:
                        logging.info('Cap {} is supported by both parties'.format(cap))
                    else:
                        client._send(':{} ERROR :Server {} is missing support for {}'.format(client.sid, client.hostname, cap))
                        client.quit('Server {} is missing support for {}'.format(client.hostname, cap))
                        return

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



@ircd.Modules.command
class Sid(ircd.Command):
    def __init__(self):
        self.command = 'sid'
        self.params = 4
        self.req_class = 'Server'


    def execute(self, client, recv):
        uplink = [s for s in self.ircd.servers if s.sid == recv[0][1:]]
        if not uplink:
            client._send(':{} ERROR :Could not find uplink for {}'.format(self.ircd.sid, recv[0][1:]))
            client.quit()
            return
        uplink = uplink[0]
        sid = recv[4]
        hostname = recv[2]
        for server in [server for server in self.ircd.servers if server.sid == sid and server != client]:
            client._send(':{} ERROR :SID {} is already in use on that network'.format(self.ircd.sid, sid))
            client.quit('SID {} is already in use on that network'.format(sid))
            return
        for server in [server for server in self.ircd.servers if server.hostname.lower() == hostname.lower() and server != client]:
            client._send(':{} ERROR :Hostname {} is already in use on that network'.format(self.ircd.sid, hostname))
            client.quit('Server {} is already in use on that network'.format(hostname))
            return

        hopcount = int(recv[3])

        if hostname == client.hostname:
            ### Own server?
            return

        from ircd import Server
        newServer = Server(origin=self.ircd, serverLink=True)

        newServer.hostname = hostname

        newServer.hopcount = hopcount
        newServer.name = ' '.join(recv[5:])[1:]

        newServer.introducedBy = client
        newServer.uplink = uplink
        newServer.sid = sid
        logging.info('{}New server added to the network: {}{}'.format(G, newServer.hostname, W))
        logging.info('{}SID: {}{}'.format(G, newServer.sid, W))
        logging.info('{}Introduced by: {} ({}) {}'.format(G, newServer.introducedBy.hostname, newServer.introducedBy.sid, W))
        logging.info('{}Uplinked to: {} ({}) {}'.format(G, newServer.uplink.hostname, newServer.uplink.sid, W))
        logging.info('{}Hopcount: {}{}'.format(G, newServer.hopcount, W))

        self.ircd.new_sync(self.ircd, client, ' '.join(recv))
