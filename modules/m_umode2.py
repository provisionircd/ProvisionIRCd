"""
/umode2 command (server)
"""

import ircd

@ircd.Modules.command
class Umode2(ircd.Command):
    def __init__(self):
        self.command = 'umode2'
        self.req_class = 'Server'

    def execute(self, client, recv):
        ### :asdf UMODE2 +ot
        target = [u for u in ircd.users if u.uid == recv[0][1:] or u.nickname == recv[0][1:]][0]
        modeset = None
        for m in recv[2]:
            if m in '+-':
                modeset = m
                continue
            if modeset == '+':
                if m not in target.modes:
                    target.modes += m

            elif modeset == '-':
                target.modes = target.modes.replace(m, '')
                if m == 'o':
                    target.operflags = []
                    target.swhois = []
                    target.opermodes = ''
                elif m == 's':
                    target.snomasks = ''

        self.ircd.new_sync(self.ircd, client, ' '.join(recv))
