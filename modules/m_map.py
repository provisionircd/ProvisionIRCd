"""
/map and /links command
"""

import ircd
import time
import datetime


@ircd.Modules.command
class Map(ircd.Command):
    """
    Displays a detailed overview of all linked servers.
    """
    def __init__(self):
        self.command = 'map'
        self.req_modes = 'o'
        self.support = [('MAP',)]

    def execute(self, client, recv):
        displayed = []
        uptime = datetime.timedelta(seconds=int(time.time()) - self.ircd.creationtime)
        usercount = len([user for user in self.ircd.users if user.server == self.ircd])
        percentage = round(100 * float(usercount)/float(len(self.ircd.users)), 2)
        client.sendraw(self.RPL.MAP, ':{:50s} {} [{}%] [Uptime: {}]'.format(self.ircd.hostname+' ('+self.ircd.sid+')', usercount, percentage, uptime))
        for s in [s for s in self.ircd.servers if s.sid]:
            if s.socket:
                usercount = len([user for user in self.ircd.users if user.server.sid == s.sid])
                percentage = round(100 * float(usercount)/float(len(self.ircd.users)), 2)
                uptime = datetime.timedelta(seconds=int(time.time()) - s.creationtime)
                client.sendraw(self.RPL.MAP, ':{:50s} {} [{}%] [Uptime: {}, lag: {}ms]'.format(s.hostname+' ('+s.sid+')', usercount, percentage, uptime, s.lag))
            for s2 in self.ircd.servers:
                if s2.introducedBy == s and s2 not in displayed:
                    usercount = len([user for user in self.ircd.users if user.server.sid == s2.sid])
                    percentage = round(100 * float(usercount)/float(len(self.ircd.users)), 2)
                    uptime = datetime.timedelta(seconds=int(time.time()) - s.creationtime)
                    client.sendraw(self.RPL.MAP, ':   |-{:50s} {} [{}%] [Uptime: {}]'.format(s2.hostname+ '('+s2.sid+')', usercount, percentage, uptime))
                    displayed.append(s2)
                    for s3 in [s3 for s3 in self.ircd.servers if s3 != s2 and s3.uplink and s3.uplink == s2]:
                        client.sendraw(self.RPL.MAP, ':   `-{:50s} ({}) {}'.format(s3.hostname, s3.sid, len([user for user in self.ircd.users if user.server.sid == s3.sid])))
                        displayed.append(s3)
        client.sendraw(self.RPL.MAPEND, ':End of /MAP')


@ircd.Modules.command
class Links(ircd.Command):
    """
    Displays an overview of all linked servers.
    """
    def __init__(self):
        self.command = 'links'
        self.req_modes = 'o'

    def execute(self, client, recv):
        for s in self.ircd.servers+[self.ircd]:
            s2 = s.uplink if s.uplink else s.introducedBy
            if not s2:
                s2 = self.ircd
            client.sendraw(self.RPL.LINKS, '{} {} :{} {}'.format(s.hostname, s2.hostname, s.hopcount, s.name))
        client.sendraw(self.RPL.ENDOFLINKS, ':End of /LINKS')
