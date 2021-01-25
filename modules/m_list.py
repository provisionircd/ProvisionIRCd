"""
/list command
"""

import ircd


@ircd.Modules.command
class List(ircd.Command):
    """
    Request a list of all channels on the network
    """

    def __init__(self):
        self.command = 'list'
        self.support = [('SAFELIST',), ('ELIST', 'U')]

    def execute(self, client, recv):
        client.flood_safe = True
        client.sendraw(self.RPL.LISTSTART, 'Channel :Users  Name')
        minusers, maxusers = None, None
        if len(recv) >= 2 and recv[1][0] in '<>' and len(recv[1]) > 1 and recv[1][1].isdigit():
            usercount = recv[1].split(',')
            for c in [c for c in usercount if len(c) > 1]:
                if c[0] == '<':
                    maxusers = c[1:]
                elif c[0] == '>':
                    minusers = c[1:]
        for channel in self.ircd.channels:
            if maxusers is not None and len(channel.users) > int(maxusers):
                continue
            if minusers is not None and len(channel.users) < int(minusers):
                continue
            if ('s' in channel.modes or 'p' in channel.modes) and (client not in channel.users and 'o' not in client.modes):
                if 'p' in channel.modes:
                    client.sendraw(self.RPL.LIST, '* {} :'.format(len(channel.users)))
                continue
            else:
                client.sendraw(self.RPL.LIST, '{} {} :[+{}] {}'.format(channel.name, len(channel.users), channel.modes, channel.topic))
        client.sendraw(self.RPL.LISTEND, ':End of /LIST')
