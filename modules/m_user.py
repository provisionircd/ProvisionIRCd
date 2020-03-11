"""
/user command
"""

import ircd

from handle.functions import match, logging


class User(ircd.Command):
    """
    Used to register your connection to the server
    """
    def __init__(self):
        self.command = 'user'
        self.params = 4


    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            # Command USER is not being used by any server. Assume normal user.
            return client.quit('This port is for servers only')

        if client.ident:
            return client.sendraw(462, ':You may not reregister')

        if 'nmap' in ''.join(recv).lower():
            return client.quit('Connection reset by peer')

        ident = str(recv[1][:12]).strip()
        realname = recv[4][:48]

        valid = "abcdefghijklmnopqrstuvwxyz0123456789-_"
        for c in ident:
            if c.lower() not in valid:
                ident = ident.replace(c, '')

        block = 0
        for cls in iter([cls for cls in self.ircd.conf['allow'] if cls in self.ircd.conf['class']]):
            t = self.ircd.conf['allow'][cls]
            isMatch = False
            if 'ip' in t:
                clientmask = '{}@{}'.format(client.ident, client.ip)
                isMatch = match(t['ip'], clientmask)
            if 'hostname' in t and not isMatch: # Try with hostname. IP has higher priority.
                clientmask = '{}@{}'.format(client.ident, client.hostname)
                isMatch = match(t['hostname'], clientmask)
            if isMatch:
                if 'options' in t:
                    if 'ssl' in t['options'] and not client.ssl:
                        continue
                client.cls = cls
                if 'block' in t:
                    for entry in t['block']:
                        clientmask_ip = '{}@{}'.format(client.ident, client.ip)
                        clientmask_host = '{}@{}'.format(client.ident, client.hostname)
                        block = match(entry, clientmask_ip) or match(entry, clientmask_host)
                        if block:
                            logging.info('Client {} blocked by {}: {}'.format(client, cls, entry))
                            break
                break

        client.ident = ident
        client.realname = realname
        if client.nickname != '*' and client.validping and (client.cap_end or not client.sends_cap):
            client.welcome()
