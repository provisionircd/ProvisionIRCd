"""
/cap command
"""

import ircd

@ircd.Modules.params(1)
@ircd.Modules.commands('cap')
def cap(self, localServer, recv):
    if recv[1].lower() in ['ls', 'list']:
        self.sends_cap = True
        caps = []
        for c in localServer.caps:
            caps.append(c)
        self._send(':{} CAP {} LS :{}'.format(localServer.hostname, self.nickname, ' '.join(caps)))
    elif recv[1].lower() == 'req':
        self.sends_cap = True
        caps = ' '.join(recv[2:])[1:].lower() if recv[2].startswith(':') else ' '.join(recv[2:]).lower()
        for cap in caps.split():
            if cap.lower() in localServer.caps and cap not in self.caplist:
                self.caplist.append(cap)
        string = ':{} CAP {} ACK :{}'.format(localServer.hostname, self.nickname, ' '.join(self.caplist))
        self._send(string)
    elif recv[1].lower() == 'end':
        self.cap_end = True
        if not self.registered and self.nickname != '*' and self.ident:
            self.welcome()
    else:
        self.sendraw(410, '{} :Unknown CAP command'.format(recv[1]))

def init(localServer, reload=False):
    localServer.caps = [
                'account-notify',
                'away-notify',
                'server-time',
                'chghost',
                'echo-message',
                'tls',
                'userhost-in-names',
                'extended-join',
                'operwatch'
        ]

'''
@ircd.Modules.hooks.welcome
def cap_operwatch(self, localServer):
    if 'operwatch' not in self.caps:
        return
    for u in [u for u in localServer.users if 'o' in u.modes]:
        self._send(':{} UMODE +o'.format(u.fullmask())
'''
