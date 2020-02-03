"""
/user command
"""

import ircd


@ircd.Modules.command
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

        client.ident = ident
        client.realname = realname
        if client.nickname != '*' and client.validping and (client.cap_end or not client.sends_cap):
            client.welcome()
