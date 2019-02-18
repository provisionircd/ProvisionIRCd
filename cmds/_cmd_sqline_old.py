# :00B SQLINE Testbot :Reserved for services
import os
import sys
import time
from cmds import cmd_tkl
TKL = cmd_tkl.TKL()

def cmd_SQLINE(self, localServer, recv):
    try:
        if type(self).__name__ != 'Server':
            self.sendraw(487, ':SQLINE is a server only command')
            return

        if len(recv) < 4:
            return

        nick = recv[2]
        reason = ' '.join(recv[3:])

        if reason.startswith(':'):
            reason = reason[1:]

        data = ':{} + Q * {} {} 0 {} :{}'.format(localServer.sid, nick, self.hostname, int(time.time()), reason)
        self.handle('tkl', data)
    except Exception as ex:
        print(ex)
