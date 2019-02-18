import sys
import gc
import objgraph

def cmd_REFCOUNT(self, localServer, recv):
    if 'o' not in self.modes:
        return
    try:
        self._send(':{} NOTICE {} :*** WARNING -- This output may cause your client to disconnect due to huge data!'.format(self.server.hostname, self.nickname))
        self._send(':{} NOTICE {} :*** Refcount: {}'.format(self.server.hostname, self.nickname, sys.getrefcount(self)))
        for r in gc.get_referrers(self):
            self._send(':{} NOTICE {} :{}'.format(self.server.hostname, self.nickname, r))
    except Exception as ex:
        print(ex)

    objgraph.show_most_common_types()
