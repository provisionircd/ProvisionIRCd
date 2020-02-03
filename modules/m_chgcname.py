"""
/chgcname command
"""

import ircd


@ircd.Modules.command
class Chgcname(ircd.Command):
    """
    Change channel name capitalisation.
    Example: /CHGCNAME #home #Home
    """
    def __init__(self):
        self.command = 'chgcname'
        self.params = 2
        self.req_modes = 'o'


    def execute(self, client, recv):
        if type(self).__name__ == 'Server':
            sourceServer = client
            client = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], self.ircd.users))[0]
            recv = recv[1:]
        else:
            sourceServer = client.server
        name = recv[2]

        channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), self.ircd.channels))
        if not channel:
            return self.ircd.notice(client, 'That channel does not exist.')

        channel = channel[0]

        if name[0] != channel.name[0]:
            return self.ircd.notice(client, 'Converting of channel type is not allowed.')

        if name == channel.name:
            return self.ircd.notice(client, 'Channel names are equal; nothing changed.')

        if name.lower() != channel.name.lower():
            return self.ircd.notice(client, 'Only case changing is allowed.')

        if sourceServer == self.ircd:
            self.ircd.notice(client, 'Channel {} successfully changed to {}'.format(channel.name, name))

        self.ircd.new_sync(self.ircd, sourceServer, ':{} CHGCNAME {} {}'.format(client.uid, channel.name, name))
        old_name = channel.name
        channel.name = name
        if sourceServer == self.ircd:
            msg = '*** {} ({}@{}) used CHGCNAME to change channel name {} to {}'.format(client.nickname, client.ident, client.hostname, old_name, name)
            self.ircd.snotice('s', msg)
