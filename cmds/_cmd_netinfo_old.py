import time
import os
import sys
import hashlib
import socket

def cmd_NETINFO(self, localServer, recv):
    try:
        if type(self).__name__ != 'Server':
            self.sendraw(487, ':NETINFO is a server only command')
            return
        source = list(filter(lambda s: s.sid == recv[0][1:], localServer.servers))[0]

        maxglobal = int(recv[2])
        remotetime = int(recv[3])
        version = recv[4]
        cloakhash = recv[5]

        remotename = recv[9][1:]
        remotehost = list(filter(lambda s: s.name == remotename, localServer.servers))
        if remotehost:
            remotehost = remotehost[0].hostname

        if maxglobal > localServer.maxgusers:
            localServer.maxgusers = maxglobal

        currenttime = int(time.time())

        if not source.socket:
            source.netinfo = True
            #localServer.replyPing[source] = True
            #print('Server {} will now reply to PING requests from {} (NETINFO)'.format(localServer.hostname,source.hostname))
            return

        if remotehost:
            if abs(remotetime-currenttime) > 10:
                if abs(remotetime-currenttime) > 120:
                    err = 'ERROR :Link denied due to incorrect clocks. Please make sure both clocks are synced!'
                    self._send(err)
                    self.quit(err)
                    return
                if remotetime > currenttime:
                    localServer.snotice('s', '*** (warning) Remote server {}\'s clock is ~{}s ahead on ours, this can cause issues and should be fixed!'.format(remotehost, abs(remotetime-currenttime)))
                elif remotetime < currenttime:
                    localServer.snotice('s', '*** (warning) Remote server {}\'s clock is ~{}s behind on ours, this can cause issues and should be fixed!'.format(remotehost, abs(remotetime-currenttime)))

            if remotename != localServer.name and source.name == remotename:
                localServer.snotice('s', '*** Network name mismatch from {} ({} != {})'.format(source.hostname, remotename, localServer.name))

            if version != localServer.versionnumber.replace('.', '') and remotehost not in localServer.conf['settings']['ulines'] and source.name == remotename:
                localServer.snotice('s', '*** Remote server {} is using version {}, and we are using version {}, but this should not cause issues.'.format(remotehost, version, localServer.versionnumber.replace('.', '')))

            if cloakhash.split(':')[1] != hashlib.md5(localServer.conf['settings']['cloak-key'].encode('utf-8')).hexdigest():
                localServer.snotice('s', '*** (warning) Network wide cloak keys are not the same! This will affect channel bans and must be fixed!')

        if not source.netinfo:
            source.netinfo = True
            if source not in localServer.linkrequester:
                ip, port = source.socket.getpeername()
                try:
                    port = localServer.conf['link'][source.hostname]['outgoing']['port']
                except:
                    pass
            else:
                ### When you requested the link.
                ip, port = source.socket.getpeername()
                del localServer.linkrequester[source]

            string = 'Secure ' if source.is_ssl else ''
            msg = '*** (link) {}Link {} -> {}[@{}.{}] successfully established'.format(string, localServer.hostname, source.hostname, ip, port)
            localServer.snotice('s', msg)

        localServer.syncToServers(localServer, self, ' '.join(recv))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)