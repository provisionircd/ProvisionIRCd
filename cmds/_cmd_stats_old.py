import sys
import os
import time
import datetime
import threading
try:
    import psutil
except ImportError:
    pass

import resource


stats = 'duCGO'

def cmd_STATS(self, localServer, recv):
    try:
        if 'o' not in self.modes:
            self.sendraw(481, ':Permission denied - You are not an IRC Operator')
            return

        if not self.ocheck('o', 'stats'):
            self.sendraw(481, ':Permission denied - You do not have the correct IRC Operator privileges')
            return

        if len(recv) == 1:
            self.sendraw(210, ':/Stats flags:')
            self.sendraw(210, ':d - Displays the local DNSBL cache')
            self.sendraw(210, ':u - View server uptime')
            self.sendraw(210, ':C - View raw server data and info')
            self.sendraw(210, ':G - View the global TKL info')
            self.sendraw(210, ':O - Send the oper block list')
            self.sendraw(219, '* :End of /STATS report')
            return

        elif recv[1] not in stats:
            self._send(':{} NOTICE {} :* STATS -- Unknown stats "{}"'.format(localServer.hostname, self.uid,recv[1]))
            return

        if recv[1] == 'C':
            self.sendraw(210, ':{} socket: {}'.format(localServer,localServer.socket))
            self.sendraw(210, ':Total connected users in local server.users list: {}'.format(len(localServer.users)))
            for u in localServer.users:
                self.sendraw(210, ':            {} on {}: {} ({}) :: refcount: {}, class: {}'.format(u.nickname, u.server.hostname, u, u.ip ,sys.getrefcount(u), u.cls if u.server == localServer else 'remote user'))
            self.sendraw(210, ':Total connected servers in local server.servers list (not including local): {}'.format(len(localServer.servers)))
            for s in list(localServer.servers):
                if not s:
                    localServer.servers.remove(s)
                    continue
                if s.sid:
                    if s.socket:
                        self.sendraw(210, ':            {} {} :: {} --- socket: {}, class: {}'.format(s.sid, s.hostname, s, s.socket, s.cls))
                    for s2 in localServer.servers:
                        if s2.introducedBy == s:
                            self.sendraw(210, ':                        ---> {} {} :: {} --- socket: {}, introduced by: {}'.format(s2.sid, s2.hostname, s2, s2.socket, s2.introducedBy))

            self.sendraw(210, ':Total channels in local server.channels list: {}'.format(len(localServer.channels)))
            for c in localServer.channels:
                self.sendraw(210, ':{} :: {}'.format(c.name,c))
                for u in c.users:
                    self.sendraw(210, ':        {} +{} :: {}'.format(u.nickname, c.usermodes[u], u.server.hostname))

            self.sendraw(210, ':Ulines: {}'.format(localServer.conf['settings']['ulines']))

        elif recv[1] == 'd':
            dnsbl = localServer.dnsblCache[:128] if len(localServer.dnsblCache) > 128 else localServer.dnsblCache
            for entry in dnsbl:
                date = '{} {}'.format(datetime.datetime.fromtimestamp(float(localServer.dnsblCache[entry]['ctime'])).strftime('%a %b %d %Y'), datetime.datetime.fromtimestamp(float(localServer.dnsblCache[entry]['ctime'])).strftime('%H:%M:%S %Z'))
                date = date.strip()
                self.sendraw(210, ':{} {} {}'.format(entry, localServer.dnsblCache[entry]['bl'], date))
            if len(dnsbl) == 128:
                self.sendraw(210, ':Showing only first 128 entries')

        elif recv[1] == 'G':
            for type in [type for type in localServer.tkl if type in 'GZQ']:
                for mask in localServer.tkl[type]:
                    self.sendraw(223, '{} {} {} {} {} :{}'.format(type, mask, int(localServer.tkl[type][mask]['expire'])-int(time.time()) if localServer.tkl[type][mask]['expire'] != '0' else '0', localServer.tkl[type][mask]['ctime'], localServer.tkl[type][mask]['setter'], localServer.tkl[type][mask]['reason']))

        elif recv[1] == 'O':
            for oper in localServer.conf['opers']:
                for operhost in localServer.conf['opers'][oper]['host']:
                    self.sendraw(243, ':{} {} * {} - {}'.format(recv[1],operhost, oper, localServer.conf['opers'][oper]['operclass']))

        elif recv[1] == 'u':
            uptime = datetime.timedelta(seconds=int(time.time()) - localServer.creationtime)
            self.sendraw(242, ':Server up: {}'.format(uptime))
            ram = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            print(ram)
            try:
                pid = os.getpid()
                py = psutil.Process(pid)
                memoryUse = float(py.memory_info()[0] /2.**20) # memory use in GB...I think
                memoryUse = "%.2f" % memoryUse
                self.sendraw(242, ':RAM usage: {} MB'.format(memoryUse))
                #self.sendraw(242,':CPU usage: {} (bugged)'.format('0.0'))
            except:
                pass

        self.sendraw(219, '{} :End of /STATS'.format(recv[1]))
        msg = '* Stats "{}" requested by {} ({}@{})'.format(recv[1], self.nickname, self.ident, self.hostname)
        localServer.snotice('s', msg)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        print(e)
