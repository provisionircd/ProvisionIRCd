"""
/netinfo command (server)
"""

import ircd

import time
import hashlib
import socket

from handle.functions import logging


@ircd.Modules.command
class Netinfo(ircd.Command):
    def __init__(self):
        self.command = 'netinfo'
        self.req_class = 'Server'
        self.params = 1


    def execute(self, client, recv):
        sid = recv[0][1:]
        #source = list(filter(lambda s: s.sid == recv[0][1:], self.ircd.servers))[0]
        source = [s for s in self.ircd.servers if s.sid == sid]
        if not source:
            logging.error('Received NETINFO from unknown server with SID: {}'.format(sid))
            logging.error('Uplink: {}'.format(client))
            logging.error('Data: {}'.format(recv))
            return
        source = source[0]

        maxglobal = int(recv[2])
        remotetime = int(recv[3])
        version = recv[4]
        cloakhash = recv[5]

        creation = int(recv[6])

        remotename = recv[9][1:]
        remotehost = list(filter(lambda s: s.name == remotename, self.ircd.servers))
        if remotehost:
            remotehost = remotehost[0].hostname

        if maxglobal > self.ircd.maxgusers:
            self.ircd.maxgusers = maxglobal

        currenttime = int(time.time())

        if not source.socket:
            source.netinfo = True
            #self.ircd.replyPing[source] = True
            #print('Server {} will now reply to PING requests from {} (NETINFO)'.format(self.ircd.hostname,source.hostname))
            return

        remotehost = source.hostname
        if abs(remotetime-currenttime) > 10:
            if abs(remotetime-currenttime) > 120:
                err = 'ERROR :Link denied due to incorrect clocks. Please make sure both clocks are synced!'
                client._send(err)
                client.quit(err)
                return
            if remotetime > currenttime:
                self.ircd.snotice('s', '*** (warning) Remote server {}\'s clock is ~{}s ahead on ours, this can cause issues and should be fixed!'.format(remotehost, abs(remotetime-currenttime)), local=True)
            elif remotetime < currenttime:
                self.ircd.snotice('s', '*** (warning) Remote server {}\'s clock is ~{}s behind on ours, this can cause issues and should be fixed!'.format(remotehost, abs(remotetime-currenttime)), local=True)

        if remotename != self.ircd.name and source.name == remotename:
            self.ircd.snotice('s', '*** Network name mismatch from {} ({} != {})'.format(source.hostname, remotename, self.ircd.name), local=True)

        if version != self.ircd.versionnumber.replace('.', '') and remotehost not in self.ircd.conf['settings']['ulines'] and source.name == remotename:
            self.ircd.snotice('s', '*** Remote server {} is using version {}, and we are using version {}, but this should not cause issues.'.format(remotehost, version, self.ircd.versionnumber.replace('.', '')), local=True)

        if cloakhash.split(':')[1] != hashlib.md5(self.ircd.conf['settings']['cloak-key'].encode('utf-8')).hexdigest():
            self.ircd.snotice('s', '*** (warning) Network wide cloak keys are not the same! This will affect channel bans and must be fixed!', local=True)

        if creation:
            source.creationtime = creation

        if not source.netinfo:
            source.netinfo = True
            if source not in self.ircd.linkrequester:
                ip, port = source.socket.getpeername()
                try:
                    port = self.ircd.conf['link'][source.hostname]['outgoing']['port']
                except:
                    pass
            else:
                ### When you requested the link.
                ip, port = source.socket.getpeername()
                del self.ircd.linkrequester[source]

            string = 'Secure ' if source.is_ssl else ''
            msg = '*** (link) {}Link {} -> {}[@{}.{}] successfully established'.format(string, self.ircd.hostname, source.hostname, ip, port)
            self.ircd.snotice('s', msg, local=True)

        self.ircd.new_sync(self.ircd, client, ' '.join(recv))
