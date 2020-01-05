"""
/sanick command
"""

import ircd

@ircd.Modules.params(2)
@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('localsacmds|globalsacmds')
@ircd.Modules.commands('sanick')
def sanick(self, localServer, recv):
    """Forcefully change a users nickname.
Syntax: /SANICK <user> <newnick>"""
    target = list(filter(lambda c: c.nickname.lower() == recv[1].lower(), localServer.users))
    if not target:
        return self.sendraw(401, '{} :No such nick'.format(recv[1]))

    if target[0].server != localServer and not self.ocheck('o', 'globalsacmds'):
        return self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')

    if target[0].nickname == recv[2]:
        return
    services = [x.lower() for x in localServer.conf['settings']['ulines']]
    services.append(localServer.conf['settings']['services'].lower())
    if 'S' in target[0].modes or target[0].server.hostname.lower() in services:
        return localServer.handle('NOTICE', '{} :*** You cannot use /SANICK on services.'.format(self.nickname))

    nick = list(filter(lambda u: u.nickname == recv[2], localServer.users))
    if nick:
        return localServer.notice(self, '*** Nickname {} is already in use'.format(nick[0].nickname))

    if recv[2][0].isdigit():
        return localServer.handle('NOTICE', '{} :*** Nicknames may not start with a number'.format(self.uid))

    self.flood_penalty += 100000
    p = {'sanick': self}
    target[0].handle('nick', recv[2], params=p)
