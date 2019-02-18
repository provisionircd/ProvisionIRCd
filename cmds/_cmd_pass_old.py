import os
import sys

import handle.handleLogs as Logger

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

def _print(txt):
    Logger.write(txt)
    #print(txt)

def cmd_PASS(self, localServer, recv):
    source = recv[0][1:]
    try:
        if type(self).__name__ == 'User' and self.registered:
            self.sendraw(462,':You may not reregister')
            return
        if len(recv) < 2:
            self.sendraw(461,':PASS Not enough parameters')
            return
        self.linkpass = recv[-1][1:]
        print('{}Password for {} set: {}{}'.format(G,self,self.linkpass,W))
        ip, port = self.socket.getpeername()
        ip2, port2 = self.socket.getsockname()

        if self.hostname:
            if self.hostname not in localServer.conf['link']:
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(self.hostname,ip,port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(localServer.hostname,ip2,port2)
                if self not in localServer.linkrequester:
                    self._send('ERROR :{}'.format(error))
                elif localServer.linkrequester[self]['user']:
                    localServer.linkrequester[self]['user'].send('NOTICE','*** {}'.format(msg))
                self.quit('no matching link configuration',silent=True)
                return

            if self.linkpass != localServer.conf['link'][self.hostname]['pass']:
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(self.hostname,ip,port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration'.format(localServer.hostname,ip2,port2)
                if self not in localServer.linkrequester:
                    self._send('ERROR :{}'.format(error))
                elif localServer.linkrequester[self]['user']:
                    localServer.linkrequester[self]['user'].send('NOTICE','*** {}'.format(msg))
                self.quit('no matching link configuration',silent=True)
                return

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R,exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj,W)
        print(e)
