#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/map and /links command
"""

import ircd

@ircd.Modules.req_modes('o')
@ircd.Modules.commands('map')
def cmd_map(self, localServer, recv):
    displayed = []
    self.sendraw('006', ':{} ({}) {}'.format(localServer.hostname, localServer.sid, len([user for user in localServer.users if user.socket])))
    for s in localServer.servers:
        if s.sid:
            if s.socket:
                self.sendraw('006', ':`-{} ({}) {}'.format(s.hostname, s.sid, len([user for user in localServer.users if user.server.sid == s.sid])))
            for s2 in localServer.servers:
                if s2.introducedBy == s and s2 not in displayed:
                    self.sendraw('006', ':   |-{} ({}) {}'.format(s2.hostname, s2.sid, len([user for user in localServer.users if user.server.sid == s2.sid])))
                    displayed.append(s2)
                    for s3 in [s3 for s3 in localServer.servers if s3 != s2 and s3.uplink and s3.uplink == s2]:
                        self.sendraw('006', ':   `-{} ({}) {}'.format(s3.hostname, s3.sid, len([user for user in localServer.users if user.server.sid == s3.sid])))
                        displayed.append(s3)
    self.sendraw('007', ':End of /MAP')

@ircd.Modules.req_modes('o')
@ircd.Modules.commands('links')
def links(self, localServer, recv):
    for s in localServer.servers+[localServer]:
        s2 = s.uplink if s.uplink else s.introducedBy
        if not s2:
            s2 = localServer
        string = '{} {} :{} {}'.format(s.hostname, s2.hostname, s.hopcount, s.name)
        self.sendraw('364', string)
    self.sendraw('365', ':End of /LINKS')
