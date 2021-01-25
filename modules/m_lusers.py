"""
/lusers command
"""

import ircd


class Lusers(ircd.Command):
    """
    View user statistics.
    """

    def __init__(self):
        self.command = 'lusers'

    def execute(self, client, recv):
        servers = len(list(filter(lambda s: s.eos, self.ircd.servers))) + 1
        ownservers = len(list(filter(lambda s: s.eos and s.socket, self.ircd.servers)))
        invisible = len(list(filter(lambda c: 'i' in c.modes, self.ircd.users)))
        opers = len(list(filter(lambda c: 'o' in c.modes and 'H' not in c.modes and 'S' not in c.modes, self.ircd.users)))
        lusers = len(list(filter(lambda u: u.server == self.ircd and u.registered, self.ircd.users)))
        gusers = len(list(filter(lambda u: u.registered, self.ircd.users)))
        unknown_users = [u for u in self.ircd.users if not u.registered]
        unknown_servers = [s for s in self.ircd.servers if not s.eos]
        unknown = len(unknown_users + unknown_servers)
        client.sendraw(self.RPL.LUSERCLIENT, ':There {} {} user{} and {} invisible on {} server{}'.format('are' if len(self.ircd.users) != 1 else 'is', len(self.ircd.users), 's' if len(self.ircd.users) != 1 else '', invisible, servers,
                                                                                                          's' if servers != 1 else ''))
        client.sendraw(self.RPL.LUSEROP, '{} :IRC Operator{} online'.format(opers, 's' if opers != 1 else ''))
        if unknown > 0:
            client.sendraw(self.RPL.LUSERUNKNOWN, '{} :unknown connection{}'.format(unknown, 's' if unknown != 1 else ''))
        client.sendraw(self.RPL.LUSERCHANNELS, '{} :channel{} in use'.format(len(self.ircd.channels), 's' if len(self.ircd.channels) != 1 else ''))
        client.sendraw(self.RPL.LUSERME, ':I have {} client{} and {} server{}'.format(lusers, 's' if lusers != 1 else '', ownservers, 's' if ownservers != 1 else ''))
        # client.sendraw(265, '{} {} :{} user{} on this server. Max: {}'.format(lusers, self.ircd.maxusers, lusers, 's' if lusers != 1 else '', self.ircd.maxusers))
        # client.sendraw(266, '{} {} :{} user{} on entire network. Max: {}'.format(len(self.ircd.users), self.ircd.maxgusers, len(self.ircd.users), 's' if len(self.ircd.users) != 1 else '', self.ircd.maxgusers))
        client.sendraw(self.RPL.LOCALUSERS, ':{} user{} on this server. Max: {}'.format(lusers, 's' if lusers != 1 else '', self.ircd.maxusers))
        client.sendraw(self.RPL.GLOBALUSERS, ':{} user{} on entire network. Max: {}'.format(gusers, 's' if gusers != 1 else '', self.ircd.maxgusers))
