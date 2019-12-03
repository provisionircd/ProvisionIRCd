#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/map and /links command
"""

import ircd
import time
import datetime

@ircd.Modules.support('MAP')
@ircd.Modules.req_modes('o')
@ircd.Modules.commands('map')
def cmd_map(self, localServer, recv):
    displayed = []
    uptime = datetime.timedelta(seconds=int(time.time()) - localServer.creationtime)
    usercount = len([user for user in localServer.users if user.server == localServer])
    percentage = round(100 * float(usercount)/float(len(localServer.users)), 2)
    self.sendraw('006', ':{:50s} {} [{}%] [Uptime: {}]'.format(localServer.hostname+' ('+localServer.sid+')', usercount, percentage, uptime))
    for s in [s for s in localServer.servers if s.sid]:
        if s.socket:
            usercount = len([user for user in localServer.users if user.server.sid == s.sid])
            percentage = round(100 * float(usercount)/float(len(localServer.users)), 2)
            uptime = datetime.timedelta(seconds=int(time.time()) - s.creationtime)
            self.sendraw('006', ':{:50s} {} [{}%] [Uptime: {}, lag: {}ms]'.format(s.hostname+' ('+s.sid+')', usercount, percentage, uptime, s.lag))
        for s2 in localServer.servers:
            if s2.introducedBy == s and s2 not in displayed:
                usercount = len([user for user in localServer.users if user.server.sid == s2.sid])
                percentage = round(100 * float(usercount)/float(len(localServer.users)), 2)
                uptime = datetime.timedelta(seconds=int(time.time()) - s.creationtime)
                self.sendraw('006', ':   |-{:50s} {} [{}%] [Uptime: {}]'.format(s2.hostname+ '('+s2.sid+')', usercount, percentage, uptime))
                displayed.append(s2)
                for s3 in [s3 for s3 in localServer.servers if s3 != s2 and s3.uplink and s3.uplink == s2]:
                    self.sendraw('006', ':   `-{:50s} ({}) {}'.format(s3.hostname, s3.sid, len([user for user in localServer.users if user.server.sid == s3.sid])))
                    displayed.append(s3)
    self.sendraw('007', ':End of /MAP')

@ircd.Modules.req_modes('o')
@ircd.Modules.commands('links')
def links(self, localServer, recv):
    for s in localServer.servers+[localServer]:
        s2 = s.uplink if s.uplink else s.introducedBy
        if not s2:
            s2 = localServer
        self.sendraw('364', '{} {} :{} {}'.format(s.hostname, s2.hostname, s.hopcount, s.name))
    self.sendraw('365', ':End of /LINKS')
