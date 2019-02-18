import os
import sys
import time

W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

def checkSid(self, localServer, sid):
    try:
        check = list(filter(lambda s: s.sid == sid, localServer.servers+[localServer]))
        if check:
            #print('{}NETWORK ERROR: SID {} already found on this network!{}'.format(R,sid,W))
            ip, port = self.socket.getsockname()
            msg = 'Error connecting to server {}[{}:{}]: SID {} is already in use by a server'.format(self.hostname, ip, port, sid)
            if self not in localServer.linkrequester:
                self._send('ERROR :{}'.format(msg))
            elif localServer.linkrequester[self]['user']:
                localServer.linkrequester[self]['user'].send('NOTICE','*** {}'.format(msg))
            #print('Quitting double SID server {}'.format(self))
            self.quit('SID {} is already in use by another server'.format(sid), silent=True)
            return

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
        print(e)

def cmd_PROTOCTL(self, localServer, recv):
    try:
        if type(self).__name__ != 'Server':
            return
        self.nextSid = None
        sid = ' '.join(recv).split('SID=')[1].split(' ')[0]
        checkSid(self, localServer, sid)
        if self.sid is None:
            self.sid = sid
        else:
            self.nextSid = sid
            print('{}SID of next incoming server set: {}{}'.format(G, self.nextSid, W))

        ### Grabbing only the non-paramental modes of the remote server.
        remoteModes = ' '.join(recv).split('CHANMODES=')[1].split(',')[3].split()[0]
        chmodes = ''.join(localServer.chmodes.split(',')[3])
        for mode in remoteModes:
            if mode not in chmodes:
                #print('{}Adding support for channel mode \'{}\'{}'.format(P,mode,W))
                chmodes += mode

            chmodes = ''.join(sorted(set(chmodes)))
            localServer.chmodes = ''.join(localServer.chmodes.split(',')[0])+','+''.join(localServer.chmodes.split(',')[1])+','+''.join(localServer.chmodes.split(',')[2])+','+chmodes

            localServer.raw005 = 'MAXTARGETS={} WATCH={} WATCHOPTS=A MODES={} CHANTYPES={} PREFIX={} CHANMODES={} MAXLIST=b:{},e:{},I:{} NICKLEN={} CHANNELLEN={} TOPICLEN={} AWAYLEN={} NETWORK={}'\
            .format(localServer.maxtargets, localServer.maxwatch, localServer.maxmodes, localServer.chantypes, localServer.chprefix, localServer.chmodes,\
            localServer.maxlist['b'], localServer.maxlist['e'], localServer.maxlist['I'],\
            localServer.nicklen, localServer.chanlen, localServer.topiclen, localServer.awaylen, localServer.name)

    except IndexError:
        pass
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = '{}EXCEPTION: {} in file {} line {}: {}{}'.format(R, exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj, W)
        print(e)
