import os
import sys

from handle.handleLink import syncData

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple


def cmd_EOS(self, localServer, recv):
    try:
        if type(self).__name__ != 'Server':
            return self.sendraw(487, ':EOS is a server only command')

        source = list(filter(lambda s: s.sid == recv[0][1:], localServer.servers))
        if not source:
            return
        source = source[0]
        if source.eos:
            if not localServer.forked:
                print('INFO: remote server sent EOS twice!')
            return
        raw = ' '.join(recv)
        localServer.syncToServers(localServer, self, raw)
        if not localServer.forked:
            print('{}EOS received by: {}{}'.format(Y, source.hostname, W))

        localServer.replyPing[source] = True
        if not localServer.forked:
            print('Server {} will now reply to PING requests from {} (EOS)'.format(localServer.hostname, source.hostname))
        for server in [server for server in localServer.servers if server != source]:
            if not localServer.forked:
                print('Sending PONG from {} to {}'.format(source.hostname, server.hostname))
            try:
                server._send(':{} PONG {}'.format(source.sid, server.hostname))
            except:
                pass
        source.eos = True
        if source.hostname.lower() in localServer.pendingLinks:
            localServer.pendingLinks.remove(source.hostname.lower())

        if source not in localServer.syncDone:
            if not localServer.forked:
                print('{}Remote server {} is done syncing! My turn...{}'.format(Y,self.hostname,W))
            #self.eos = True
            s = syncData(localServer,self,serverIntroducer=None,selfRequest=False)
            s.start()
            s.join()
            #source.introducedBy = self
            #print('Setting introducedBy for {} with EOS to: {}'.format(source.hostname,self.hostname))
            return

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        if not localServer.forked:
            print(e)