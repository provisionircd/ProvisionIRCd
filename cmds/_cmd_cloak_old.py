from handle.functions import cloak

def cmd_CLOAK(self, localServer, recv):
    if 'o' not in self.modes:
        self.sendraw(481, ':Permission denied - You are not an IRC Operator')
        return

    if len(recv) < 2:
        self.sendraw(461, ':CLOAK Not enough parameters')
        return

    localServer.notice(self, '* Cloaked version is: {}'.format(cloak(localServer, recv[1])))
