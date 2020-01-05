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

@ircd.Modules.params(5)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('server')
def server(self, localServer, recv):
    try:
        exists = list(filter(lambda s: s.hostname.lower() == recv[2].lower(), localServer.servers+[localServer]))
        if exists and self != exists[0]:
            logging.error('Server {} already exists on this network2'.format(recv[2]))
            #self.quit('Server already exists on this network')
            return
        if not self.sid:
            logging.error('Direct link with {} denied because their SID is unknown to me'.format(recv[2]))
            self.quit('No SID received')
            return

        if not self.linkAccept and not self.eos:
            self.linkAccept = True
            tempName = ' '.join(recv).split(':')[-2]
            self.hostname = tempName.split()[-2].strip()
            self.hopcount = int(tempName.split()[-1])
            self.name = ' '.join(recv[4:])
            self.rawname = ' '.join(recv[3:])
            if self.name.startswith(':'):
                self.name = self.name[1:]

            logging.info('{}Hostname for {} set: {}{}'.format(G, self, self.hostname, W))
            logging.info('{}Server name for {} set: {}{}'.format(G, self, self.name, W))
            logging.info('{}Hopcount for {} set: {}{}'.format(G, self, self.hopcount, W))
            logging.info('{}SID for {} set: {}{}'.format(G, self, self.sid, W))

            ip, port = self.socket.getpeername()
            ip2, port2 = self.socket.getsockname()
            if self.hostname not in localServer.conf['link']:
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: not found in conf'.format(self.hostname, ip, port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration1'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send(':{} ERROR :{}'.format(localServer.sid, error))
                elif localServer.linkrequester[self]:
                    localServer.linkrequester[self].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration1')
                return

            self.cls = localServer.conf['link'][self.hostname]['class']
            logging.info('{}Class: {}{}'.format(G, self.cls, W))
            if not self.cls:
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: remote server has no class'.format(self.hostname, ip, port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration1'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send(':{} ERROR :{}'.format(localServer.sid, error))
                elif localServer.linkrequester[self]:
                    localServer.linkrequester[self].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration')
                return
            totalClasses = list(filter(lambda s: s.cls == self.cls, localServer.servers))
            if len(totalClasses) > int(localServer.conf['class'][self.cls]['max']):
                self.quit('Maximum server connections for this class reached')
                return

            if self.linkpass:
                if self.linkpass != localServer.conf['link'][self.hostname]['pass']:
                    msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: wrong password'.format(self.hostname, ip, port)
                    error = 'Error connecting to server {}[{}:{}]: no matching link configuration2'.format(localServer.hostname, ip2, port2)
                    if self not in localServer.linkrequester:
                        self._send(':{} ERROR :{}'.format(localServer.sid, error))
                    elif localServer.linkrequester[self]:
                        localServer.linkrequester[self].send('NOTICE', '*** {}'.format(msg))
                    self.quit('no matching link configuration2')
                    return
            if not match(localServer.conf['link'][self.hostname]['incoming']['host'], ip):
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration: incoming IP does not match'.format(self.hostname, ip, port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration3'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send(':{} ERROR :{}'.format(localServer.sid, error))
                elif localServer.linkrequester[self]:
                    localServer.linkrequester[self].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration3')
                return

            if self.hostname not in localServer.conf['settings']['ulines']:
                for cap in [cap.split('=')[0] for cap in localServer.server_support]:
                    if cap in self.protoctl:
                        logging.info('Cap {} is supported by both parties'.format(cap))
                    else:
                        self._send(':{} ERROR :Server {} is missing support for {}'.format(self.sid, self.hostname, cap))
                        self.quit('Server {} is missing support for {}'.format(self.hostname, cap))
                        return

            selfIntroduction(localServer, self)
            data = ':{} SID {} 1 {} {}'.format(localServer.sid, self.hostname, self.sid, self.name)
            localServer.new_sync(localServer, self, data)
            for server in [server for server in localServer.servers if server.sid and server != self and server.eos]:
                sid = localServer.sid if server.socket else server.uplink.sid
                data = ':{} SID {} {} {} :{}'.format(sid, server.hostname, int(server.hopcount) + 1, server.sid, server.name)
                self._send(data)

            if hasattr(self, 'outgoing') and self.outgoing:
                syncData(localServer, self)
            return

    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.params(4)
@ircd.Modules.req_class('Server')
@ircd.Modules.commands('sid')
def sid(self, localServer, recv):
    try:
        uplink = [s for s in localServer.servers if s.sid == recv[0][1:]]
        if not uplink:
            self._send(':{} ERROR :Could not find uplink for {}'.format(localServer.sid, recv[0][1:]))
            self.quit()
            return
        uplink = uplink[0]
        sid = recv[4]
        hostname = recv[2]
        for server in [server for server in localServer.servers if server.sid == sid and server != self]:
            self._send(':{} ERROR :SID {} is already in use on that network'.format(localServer.sid, sid))
            self.quit('SID {} is already in use on that network'.format(sid))
            return
        for server in [server for server in localServer.servers if server.hostname.lower() == hostname.lower() and server != self]:
            self._send(':{} ERROR :Hostname {} is already in use on that network'.format(localServer.sid, hostname))
            self.quit('Server {} is already in use on that network'.format(hostname))
            return

        hopcount = int(recv[3])

        if hostname == self.hostname:
            ### Own server?
            return

        from ircd import Server
        newServer = Server(origin=localServer, serverLink=True)

        newServer.hostname = hostname

        newServer.hopcount = hopcount
        newServer.name = ' '.join(recv[5:])[1:]

        newServer.introducedBy = self
        newServer.uplink = uplink
        newServer.sid = sid
        logging.info('{}New server added to the network: {}{}'.format(G, newServer.hostname, W))
        logging.info('{}SID: {}{}'.format(G, newServer.sid, W))
        logging.info('{}Introduced by: {} ({}) {}'.format(G, newServer.introducedBy.hostname, newServer.introducedBy.sid, W))
        logging.info('{}Uplinked to: {} ({}) {}'.format(G, newServer.uplink.hostname, newServer.uplink.sid, W))
        logging.info('{}Hopcount: {}{}'.format(G, newServer.hopcount, W))

        localServer.new_sync(localServer, self, ' '.join(recv))

    except Exception as ex:
        logging.exception(ex)
