"""
/kill command
"""

import ircd

from handle.functions import match

@ircd.Modules.command
class Kill(ircd.Command):
    """
    Forcefully disconnect a user from the server.
    Syntax: /KILL <user> <reason>
    """
    def __init__(self):
        self.command = ['kill', 'avadakedavra']
        self.req_flags = 'localkill|globalkill'
        self.params = 2

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            target = list(filter(lambda u: u.nickname.lower() == recv[2].lower() or u.uid.lower() == recv[2].lower(), self.ircd.users))
            if not target:
                return

            S = recv[0][1:]
            source = [s for s in self.ircd.servers+[self.ircd] if s.sid == S or s.hostname == S]+[u for u in self.ircd.users if u.uid == S or u.nickname == S]
            if not source:
                return
            source = source[0]
            if type(source).__name__ == 'User':
                sourceID = source.uid
                path = source.nickname
            else:
                sourceID = source.sid
                path = source.hostname

            reason = quitmsg = ' '.join(recv[3:])[1:]
            quitmsg = '[{}] Global kill by {} ({})'.format(client.hostname, path, reason)

            if target[0].socket:
                target[0].sendraw(self.RPL.TEXT, '{}'.format(':[{}] {}'.format(path, reason)))
            data = ':{} KILL {} :{}'.format(sourceID, target[0].uid, reason)
            self.ircd.new_sync(self.ircd, client, data)
            target[0].quit(quitmsg, kill=True)
            return

        target = list(filter(lambda c: c.nickname.lower() == recv[1].lower() or c.uid.lower() == recv[1].lower(), self.ircd.users))
        if not target:
            return client.sendraw(self.ERR.NOSUCHNICK, '{} :No such nick'.format(recv[1]))

        if target[0].server != self.ircd and not client.ocheck('o', 'globalkill'):
            return client.sendraw(self.ERR.NOPRIVILEGES, ':Permission denied - You do not have the correct IRC Operator privileges')

        if 'except' in self.ircd.conf and 'kill' in self.ircd.conf['except'] and type(client).__name__ != 'Server':
            check_host = '{}@{}'.format(target[0].ident, target[0].hostname)
            for e in self.ircd.conf['except']['kill']:
                if match(e, check_host):
                    self.ircd.notice(client, '*** User {} matches a kill-except ({}) and cannot be killed'.format(target[0].nickname, e))
                    return

        reason = ' '.join(recv[2:])
        if reason.startswith(':'):
            reason = reason[1:]

        path = client.nickname
        self.ircd.notice(target[0], '*** You are being disconnected from this server: [{}] ({})'.format(path, reason))
        if target[0].socket:
            target[0].sendraw(self.RPL.TEXT, '{}'.format(':[{}] {}'.format(path, reason)))
        msg = '*** Received kill msg for {} ({}@{}) Path {} ({})'.format(target[0].nickname, target[0].ident, target[0].hostname, path, reason)
        self.ircd.snotice('k', msg)

        quitmsg = '[{}] {} kill by {} ({})'.format(client.server.hostname, 'Local' if target[0].server == self.ircd else 'Global', client.nickname, reason)
        #data = ':{} KILL {} :{}'.format(client.uid, target[0].uid, quitmsg)
        data = ':{} KILL {} :{}'.format(client.uid, target[0].uid, reason)
        self.ircd.new_sync(self.ircd, client.server, data)
        target[0].quit(quitmsg, kill=True)
