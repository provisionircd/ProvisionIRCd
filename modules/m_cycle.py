"""
/cycle command
"""

import ircd


@ircd.Modules.command
class Cycle(ircd.Command):
    """
    Parts and rejoins the channel.
    """

    def __init__(self):
        self.command = 'cycle'
        self.params = 1

    def execute(self, client, recv):
        for chan in recv[1].split(','):
            channel = list(filter(lambda c: c.name.lower() == chan.lower(), client.channels))
            if not channel:
                client.sendraw(442, '{} :You\'re not on that channel'.format(chan))
                continue

            channel = channel[0]
            p = {'reason': 'Cycling'}
            client.handle('PART', channel.name, params=p)
            client.handle('JOIN', '{}'.format(channel.name))
