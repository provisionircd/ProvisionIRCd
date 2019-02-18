import os
import sys

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
G = '\033[32m' # green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

from handle.handleLink import syncData, selfIntroduction

def match(first, second):
    if len(first) == 0 and len(second) == 0:
        return True
    if len(first) > 1 and first[0] == '*' and len(second) == 0:
        return False
    if (len(first) > 1 and first[0] == '?') or (len(first) != 0
        and len(second) != 0 and first[0] == second[0]):
            return match(first[1:], second[1:])
    if len(first) != 0 and first[0] == '*':
        return match(first[1:], second) or match(first, second[1:])
    return False

def cmd_SERVER(self, localServer, recv):
    print('SERVER COMMAND: {}'.format(recv))
    try:
        if type(self).__name__ != 'Server':
            self.sendraw(487, ':SERVER is a server only command')
            return

        if len(recv) < 4:
            self.sendraw(461, ':SERVER Not enough parameters')
            return

        exists = list(filter(lambda s: s.hostname.lower() == recv[2].lower(), localServer.servers+[localServer]))
        if exists:
            if localServer.forked:
                print('Server {} already exists on this network2'.format(recv[2]))
            #self.quit('Server already exists on this network')
            return

        sid = recv[0][1:]
        source = list(filter(lambda s: s.sid == sid, localServer.servers))

        ### To accept additional servers, check to see if source server is already linked.
        ### Servers introduced by the source do not require authentication.
        print('linkAccept? {}'.format(self.linkAccept))
        if not self.linkAccept and not self.eos:
            self.linkAccept = True
            tempName = ' '.join(recv).split(':')[-2]
            self.hostname = tempName.split()[-2].strip()
            self.hopcount = tempName.split()[-1]
            self.name = ' '.join(recv).split(':')[-1]
            #self.introducedBy = localServer

            print('{}Hostname for {} set: {}{}'.format(G,self,self.hostname,W))
            print('{}Server name for {} set: {}{}'.format(G,self,self.name,W))
            print('{}Hopcount for {} set: {}{}'.format(G,self,self.hopcount,W))
            ### Assign the class.
            self.cls = localServer.conf['link'][self.hostname]['class']
            print('Class: {}'.format(self.cls))

            totalClasses = list(filter(lambda s: s.cls == self.cls, localServer.servers))
            if len(totalClasses) > int(localServer.conf['class'][self.cls]['max']):
                self.quit('Maximum server connections for this class reached')
                return

            ip, port = self.socket.getpeername()
            ip2, port2 = self.socket.getsockname()

            if self.hostname not in localServer.conf['link']:
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration1'.format(self.hostname, ip, port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration1'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send('ERROR :{}'.format(error))
                elif localServer.linkrequester[self]['user']:
                    localServer.linkrequester[self]['user'].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration1', silent=True)
                return
            if self.linkpass:
                print('compare pass')
                if self.linkpass != localServer.conf['link'][self.hostname]['pass']:
                    msg = 'Error connecting to server {}[{}:{}]: no matching link configuration2'.format(self.hostname, ip, port)
                    error = 'Error connecting to server {}[{}:{}]: no matching link configuration2'.format(localServer.hostname, ip2, port2)
                    if self not in localServer.linkrequester:
                        self._send('ERROR :{}'.format(error))
                    elif localServer.linkrequester[self]['user']:
                        localServer.linkrequester[self]['user'].send('NOTICE', '*** {}'.format(msg))
                    self.quit('no matching link configuration2',silent=True)
                    return
            if not match(localServer.conf['link'][self.hostname]['incoming']['host'],ip):
                msg = 'Error connecting to server {}[{}:{}]: no matching link configuration3'.format(self.hostname, ip,port)
                error = 'Error connecting to server {}[{}:{}]: no matching link configuration3'.format(localServer.hostname, ip2, port2)
                if self not in localServer.linkrequester:
                    self._send('ERROR :{}'.format(error))
                elif localServer.linkrequester[self]['user']:
                    localServer.linkrequester[self]['user'].send('NOTICE', '*** {}'.format(msg))
                self.quit('no matching link configuration3', silent=True)
                return

            if self in localServer.syncDone:
                #print('{}Received SERVER command from remote server {}, but I have already synced to it.{}'.format(R,self.hostname,W))
                return

            if self in localServer.linkrequester:
                ### This must also being triggered upon auto-link.
                s = syncData(localServer, self, None)
                s.start()
                s.join()
            else:
                s = selfIntroduction(localServer, self)
                s.start()
                s.join()
                return

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
        if not localServer.forked:
            print(e)
