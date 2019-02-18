import os,sys
W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

def cmd_MD(self, localServer, recv):
    if type(self).__name__ != 'Server':
        self.sendraw(487, ':MD is a server only command')
        return
    server = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], localServer.servers))
    if not server:
        return
    # :irc.foonet.com MD client 001HBEI01 certfp :a6fc0bd6100a776aa3266ed9d5853d6dce563560d8f18869bc7eef811cb2d413

    if recv[2] == 'client':
        user = list(filter(lambda u: u.uid == recv[3], localServer.users))
        if user == []:
            return
        if recv[4] == 'certfp':
            user[0].fingerprint = recv[5][1:]
            #print('{}SSL fingerprint for remote user {} set: {}{}'.format(B,user[0].nickname,user[0].fingerprint,W))
        elif recv[4] == 'operaccount':
            user[0].operaccount = recv[5][1:]
            #print('{}Oper account for remote user {} set: {}{}'.format(B,user[0].nickname,user[0].operaccount,W))

    localServer.syncToServers(localServer,self,' '.join(recv))