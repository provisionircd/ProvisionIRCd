"""
/jump command
"""

import ircd

@ircd.Modules.command
class Jump(ircd.Command):
    """
    Attempts to redirect a user to another server.
    This will only work with some clients, like mIRC
    Syntax: JUMP <nick> <server:port>
    """
    def __init__(self):
        self.command = 'jump'
        self.req_flags = 'jump'
        self.params = 2

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            source = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], self.ircd.users))[0]
            sourceServer = client
            recv = recv[1:]
        else:
            source = client
            sourceServer = client.server

        target = list(filter(lambda c: c.nickname.lower() == recv[1].lower() or c.uid.lower() == recv[1].lower(), self.ircd.users))
        if not target:
            return client.sendraw(self.ERR.NOSUCHNICK, '{} :No such nick'.format(recv[1]))

        target = target[0]
        validPort = False
        server = recv[2]
        if '.' not in server:
            return client._send(':{} NOTICE {} :Invalid server "{}"'.format(self.ircd.hostname, source.uid,server))

        port = recv[3]
        if '+' in port and port.startswith('+'):
            validPort = True
        if port.isdigit():
            port = int(port)
            validPort = True
            if port < 0 and port > 65535:
                validPort = False

        if not validPort:
            return client._send(':{} NOTICE {} :Invalid port "{}"'.format(self.ircd.hostname, source.uid, port))

        port = int(port)
        reason = 'User has been redirected to another server ([{} {}])'.format(server, port)
        msg = '*** {} ({}@{}) used JUMP to attempt to redirect {} to {} {}'.format(source.nickname, source.ident, source.hostname, target.nickname, server, port)
        self.ircd.snotice('s', msg)
        #data = ':{} NOTICE {} :*** Notice -- You are being redirected to {}, so goodbye'.format(self.ircd.hostname, target.uid, server)
        #target._send(data)
        target.sendraw('010', '{} {}'.format(server,port))
        data = ':{} {}'.format(source.uid,' '.join(recv))
        self.ircd.new_sync(self.ircd, sourceServer, data)
