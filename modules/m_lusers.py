#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/lusers command
"""

import ircd

@ircd.Modules.commands('lusers')
def lusers(self, localServer, recv):
    servers = len(list(filter(lambda s: s.eos, localServer.servers))) + 1
    ownservers = len(list(filter(lambda s: s.eos and s.socket, localServer.servers)))
    invisible = len(list(filter(lambda c: 'i' in c.modes, localServer.users)))
    opers = len(list(filter(lambda c: 'o' in c.modes and 'H' not in c.modes and 'S' not in c.modes, localServer.users)))
    lusers = len(list(filter(lambda u: u.server == localServer and u.registered, localServer.users)))
    unknown_users = [u for u in localServer.users if not u.registered]
    unknown_servers = [s for s in localServer.servers if not s.eos]
    unknown = len(unknown_users+unknown_servers)
    self.sendraw(251, ':There {} {} user{} and {} invisible on {} server{}'.format('are' if len(localServer.users) != 1 else 'is', len(localServer.users), 's' if len(localServer.users) != 1 else '', invisible, servers, 's' if servers != 1 else ''))
    self.sendraw(252, '{} :IRC Operator{} online'.format(opers, 's' if opers != 1 else ''))
    if unknown > 0:
        self.sendraw(253, '{} :unknown connection{}'.format(unknown, 's' if unknown != 1 else ''))
    self.sendraw(254, '{} :channel{} in use'.format(len(localServer.channels), 's' if len(localServer.channels) != 1 else ''))
    self.sendraw(255, ':I have {} client{} and {} server{}'.format(lusers, 's' if lusers != 1 else '', ownservers, 's' if ownservers != 1 else ''))
    #self.sendraw(265, '{} {} :{} user{} on this server. Max: {}'.format(lusers, localServer.maxusers, lusers, 's' if lusers != 1 else '', localServer.maxusers))
    #self.sendraw(266, '{} {} :{} user{} on entire network. Max: {}'.format(len(localServer.users), localServer.maxgusers, len(localServer.users), 's' if len(localServer.users) != 1 else '', localServer.maxgusers))
    self.sendraw(265, ':{} user{} on this server. Max: {}'.format(lusers, 's' if lusers != 1 else '', localServer.maxusers))
    self.sendraw(266, ':{} user{} on entire network. Max: {}'.format(len(localServer.users), 's' if len(localServer.users) != 1 else '', localServer.maxgusers))
