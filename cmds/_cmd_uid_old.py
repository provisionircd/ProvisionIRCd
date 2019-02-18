import os
import sys
import time

from cmds import cmd_tkl
TKL = cmd_tkl.TKL()

import handle.handleLogs as Logger

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

def _print(txt,server=None):
    Logger.write(txt)
    if server and not server.forked:
        print(txt)
        
def cmd_UID(self, localServer, recv):
    #print('liefde')
    #_print('>>> {}'.format(' '.join(recv)))
    try:
        ### This should be at the start of every command, where source = where the command came from.
        if type(self).__name__ != 'Server':
            self.sendraw(487, ':UID is a server only command')
            return

       ### :001 UID Sirius 1 1518982877 provision 109.201.133.76 001R909JRYW 0 +oixzshqW * root.provisionweb.org 109.201.133.76 :.
        source = list(filter(lambda s: s.sid == recv[0][1:], localServer.servers))[0]
        nick = recv[2]
        uid = recv[7]
        params = []
        for p in recv:
            params.append(p)
        if nick.lower() in [user.nickname.lower() for user in localServer.users] and not self.eos:
            user = list(filter(lambda c: c.nickname.lower() == nick.lower(), localServer.users))[0]
            if not localServer.forked:
                print('{}WARNING: user {} already found on {}{}'.format(R,user.nickname,user.server.hostname,W))
            localUserClass = list(filter(lambda c: c.nickname.lower() == nick.lower() and c.server.hostname == localServer.hostname, localServer.users))[0]
            localTS = int(localUserClass.signon)
            remoteTS = int(recv[4])
            if remoteTS < localTS:
                if not localServer.forked:
                    print('{}Local user {} disconnected from local server.{}'.format(R,localUserClass.nickname,W))
                localUserClass.quit('Local Nick Collision')
            elif localTS <= remoteTS:
                if not localServer.forked:
                    print('{}Local user {} is dominant. Sending kill to remote servers.{}'.format(B,localUserClass.nickname,W))

                localServer.syncToServers(localServer,source,':{} . Nick Collision'.format(uid))
                return
        from ircd import User

        u = User(self, serverClass=localServer, params=params)
        
        TKL.check(localServer,u,'Z')
        TKL.check(localServer,u,'K')

        cmd = ' '.join(recv)

        if not source.allowUidSjoinSync:
            if not localServer.forked:
                print('Experimental: Server {} is not introduced yet, temporary storing UID data.'.format(source.hostname))
            source.tempSync.append(cmd)
        else:
            #localServer.handle('PRIVMSG','#Debug :<<< {}'.format(cmd))

            localServer.syncToServers(localServer,self,cmd)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        if not localServer.forked:
            print(e)