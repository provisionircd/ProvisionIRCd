"""
/cap command
"""

import ircd

from handle.functions import logging


@ircd.Modules.command
class Cap(ircd.Command):
    def __init__(self):
        self.command = 'cap'

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            return

        if recv[1].lower() in ['ls', 'list']:
            client.sends_cap = True
            caps = []
            for c in self.ircd.caps:
                caps.append(c)
            client._send(':{} CAP {} LS :{}'.format(self.ircd.hostname, client.nickname, ' '.join(caps)))
        elif recv[1].lower() == 'req':
            client.sends_cap = True
            caps = ' '.join(recv[2:])[1:].lower() if recv[2].startswith(':') else ' '.join(recv[2:]).lower()
            for cap in caps.split():
                if cap.lower() in self.ircd.caps and cap not in client.caplist:
                    client.caplist.append(cap)
                    string = ':{} CAP {} ACK :{}'.format(self.ircd.hostname, client.nickname, cap)
                    logging.debug('CAP {} ACK for {}'.format(cap, client))
                    client._send(string)

        elif recv[1].lower() == 'end':
            client.cap_end = True
            if not client.registered and client.nickname != '*' and client.ident:
                client.welcome()
        else:
            client.sendraw(410, '{} :Unknown CAP command'.format(recv[1]))
