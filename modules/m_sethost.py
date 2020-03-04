"""
/sethost command
"""

import ircd

class Sethost(ircd.Command):
    def __init__(self):
        self.command = 'sethost'
        self.param = 1
        self.req_modes = 'o'

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            source = client
            client = next((u for u in self.ircd.users if u.uid == recv[0][1:] or u.nickname == recv[0][1:]), None)
            if not client:
                return
            recv = recv[1:]
            host = str(recv[1]).strip()
            client.setinfo(host, t='host', source=source)
            return
        else:
            source = self.ircd

        host = str(recv[1][:64]).strip()
        valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
        for c in str(host):
            if c.lower() not in valid:
                host = host.replace(c, '')
        if host and host != client.cloakhost:
            client.setinfo(host, t='host', source=source)
            self.ircd.notice(client, '*** Your hostname is now "{}"'.format(client.cloakhost))
