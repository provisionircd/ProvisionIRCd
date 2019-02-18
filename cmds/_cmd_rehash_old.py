import gc
import handle.handleConf

def cmd_REHASH(self, localServer, recv):
    if 'o' not in self.modes:
        self.sendraw(481, ':Permission denied - You are not an IRC Operator')
        return
    if not self.ocheck('o', 'rehash'):
        self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
        return
    msg = '*** {} ({}@{}) is rehashing the server configuration file...'.format(self.nickname, self.ident, self.hostname)
    self.server.snotice('s', msg)

    if True:
        ### Need to add some param shit, now too lazy and hot.
        localServer.dnsblCache = {}
        localServer.throttle = {}
        localServer.hostcache = {}

    c = handle.handleConf.checkConf(localServer, self, localServer.confdir, localServer.conffile, rehash=True)
    c.start()

    gc.collect()
    del gc.garbage[:]
