"""
/setname command
"""

import ircd


class Setname(ircd.Command):
    """
    Changes your real name (GECOS field).
    """

    def __init__(self):
        self.command = 'setname'
        self.params = 1
        self.req_modes = 'o'

    def execute(self, client, recv):
        if type(client).__name__ == 'Server':
            source = client
            client = next((u for u in self.ircd.users if u.uid == recv[0][1:] or u.nickname == recv[0][1:]), None)
            if not client:
                return
            recv = recv[1:]
            realname = ' '.join(recv[1:]).rstrip()[1:]
            client.realname = realname
            self.ircd.new_sync(self.ircd, source, ':{} SETNAME :{}'.format(client.uid, client.realname))
            return

        realname = ' '.join(recv[1:])[:48].rstrip()
        if realname and realname != client.realname:
            client.realname = realname
            self.ircd.notice(client, '*** Your realname is now "{}"'.format(client.realname))
            self.ircd.new_sync(self.ircd, client.server, ':{} SETNAME :{}'.format(client.uid, client.realname))
