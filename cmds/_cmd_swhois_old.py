import os,sys
W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
Y  = '\033[33m' # yellow
B  = '\033[34m' # blue
P  = '\033[35m' # purple

def cmd_SWHOIS(self, localServer, recv):
    if type(self).__name__ != 'Server':
        self.sendraw(487,':SWHOIS is a server only command')
        return
    ### :source SWHOIS target :line
    ### :source SWHOIS target :
    server = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], localServer.servers))
    if not server:
        return
    server = server[0]
    user = list(filter(lambda u: u.uid == recv[2] or u.nickname == recv[2], localServer.users))
    if not user:
        return
    user = user[0]
    swhois = ' '.join(recv[3:])[1:]
    if not swhois:
        user.swhois = []
    else:
        if swhois not in user.swhois:
            user.swhois.append(swhois)
            
    localServer.syncToServers(localServer,self,' '.join(recv))
