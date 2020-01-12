"""
/user command
"""

import ircd

@ircd.Modules.params(4)
@ircd.Modules.commands('user')
def user(self, localServer, recv):
    """Used to register your connection to the server."""
    if type(self).__name__ == 'Server':
        # Command USER is not being used by any server. Assume normal user.
        return self.quit('This port is for servers only')

    if self.ident:
        return self.sendraw(462, ':You may not reregister')

    if 'nmap' in ''.join(recv).lower():
        return self.quit('Connection reset by peer')

    ident = str(recv[1][:12]).strip()
    realname = recv[4][:48]

    valid = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    for c in ident:
        if c.lower() not in valid:
            ident = ident.replace(c, '')

    self.ident = ident
    self.realname = realname
    if self.nickname != '*' and self.validping and (self.cap_end or not self.sends_cap):
        self.welcome()
