"""
blocks /list commands for newly connected users
"""

import ircd
import time

delay = 60

@ircd.Modules.hooks.pre_command('list')
def delaylist(self, localServer, recv):
    if int(time.time()) - self.signon < delay and 'o' not in self.modes:
        localServer.notice(self, '*** Please wait a while before requesting channel list.')
        self.sendraw(323, ':End of /LIST')
        return 0
