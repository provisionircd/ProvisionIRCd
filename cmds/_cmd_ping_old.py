import os
import sys
import time

from handle.handleLink import syncData, selfIntroduction, syncChannels
from handle.functions import _print
import handle.handleLogs as Logger

def cmd_PING(self, localServer, recv):
    try:
        if len(recv) < 2:
            self.sendraw(461,':PING Not enough parameters')
            return

        if type(self).__name__ == 'Server':
            if len(recv) == 2:
                #print('This should never happen')
                dest = list(filter(lambda s: s.sid == recv[1][1:] or s.hostname ==recv[1][1:], localServer.servers))[0].hostname
                data = ':{} PONG {}'.format(localServer.sid,dest.hostname)
                self._send(data)
                return
            source = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname ==recv[0][1:], localServer.servers))
            if not source:
                return
                #print('PING received from unknown server {}'.format(recv[0][1:]))
            else:
                source = source[0]
            dest = list(filter(lambda s: s.sid == recv[3] or s.hostname == recv[3], localServer.servers))
            if not dest:
                dest = localServer
            else:
                dest = dest[0]


            #source.ping = int(time.time())
            #print('PING from: {}, to {}, ping for {} reset. Ping now: {}'.format(source.hostname,dest.hostname,source.hostname,source.ping))
            if source not in dest.replyPing:
                ### dest.eos will NOT work! So stop trying.
                if not localServer.forked:
                    print('Server {} is not done syncing to to {} yet, not replying to PING...'.format(dest.hostname,source.hostname))
                if source not in localServer.syncDone:
                    #print('Starting syncData from PING command')
                    s = syncData(localServer,source,None)
                    s.start()
                    s.join()
                return

            data = ':{} PONG {} {}'.format(dest.sid,dest.hostname,recv[2])
            self._send(data)

        else:
            self._send(':{} PONG {} :{}'.format(localServer.hostname, localServer.hostname, recv[1]))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        #print(e)
