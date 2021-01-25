"""
/names command
"""

import ircd

from handle.functions import _print


@ircd.Modules.command
class Names(ircd.Command):
    """
    Lists all users on the given channel.
    Syntax: NAMES <channel>
    """

    def __init__(self):
        self.command = 'names'
        self.params = 1

    def execute(self, client, recv, override=False, flood_safe=False):
        channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), self.ircd.channels))
        if not channel:
            return client.sendraw(401, '{} :No such channel'.format(recv[1]))

        channel = channel[0]

        users = []
        for user in channel.users:
            if 'i' in user.modes and (client not in channel.users and not client.ocheck('o', 'override') and not override):
                continue
            if '^' in user.modes:
                if not client.ocheck('o', 'stealth'):
                    continue
                else:
                    users.append('!' + user.nickname)
                continue

            ### Check module hooks for visible_in_channel()
            visible = 1
            if user != client:
                for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'visible_in_channel']:
                    try:
                        visible = callable[2](client, self.ircd, user, channel)
                    except Exception as ex:
                        _print('Exception in module: {}: {}'.format(callable[2], ex), server=self.ircd)
            if not visible:
                continue

            prefix = ''
            for mode in [mode for mode in self.ircd.chprefix if mode in channel.usermodes[user]]:
                prefix += self.ircd.chprefix[mode]

            string = ''
            if 'userhost-in-names' in client.caplist:
                string = '!{}@{}'.format(user.ident, user.cloakhost)
            entry = '{}{}'.format(user.nickname, string)
            users.append(prefix + '' + entry)

            if flood_safe:
                client.flood_safe = True
            if len(users) >= 24:
                if flood_safe:
                    client.flood_safe = True
                client.sendraw(353, '= {} :{}'.format(channel.name, ' '.join(users)))
                users = []
                continue

        client.sendraw(353, '= {} :{}'.format(channel.name, ' '.join(users)))
        client.sendraw(366, '{} :End of /NAMES list.'.format(channel.name))
