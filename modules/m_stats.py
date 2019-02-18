#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/stats command
"""

import ircd

import sys
import os
import time
import datetime
import threading
try:
    import psutil
except ImportError:
    pass

#import resource
#import objgraph

stats = 'duCGO'

@ircd.Modules.req_modes('o')
@ircd.Modules.req_flags('stats')
@ircd.Modules.commands('stats')
def show_stats(self, localServer, recv):
    try:
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
            self._send(':{} NOTICE {} :* STATS -- Unknown stats "{}"'.format(localServer.hostname, self.uid, recv[1]))
            return

        if recv[1] == 'C':
            self.sendraw(210, ':{} socket: {}'.format(localServer, localServer.socket))
            self.sendraw(210, ':Total connected users in local server.users list: {}'.format(len(localServer.users)))
            for u in localServer.users:
                hopcount = 0 if u.server == localServer else u.server.hopcount
                self.sendraw(210, ':            {} ({}) :: refcount: {}, class: {}, hopcount: {}'.format(u, u.ip ,sys.getrefcount(u), u.cls if u.server == localServer else 'remote user', hopcount))
            self.sendraw(210, ':Total connected servers in local server.servers list (not including local): {}'.format(len(localServer.servers)))
            displayed = []
            for s in localServer.servers:
                if s.sid:
                    if s.socket:
                        self.sendraw(210, ':            {} {} :: {} --- socket: {}, class: {}'.format(s.sid, s.hostname, s, s.socket, s.cls))
                    for s2 in localServer.servers:
                        if s2.introducedBy == s and s2 not in displayed:
                            self.sendraw(210, ':                        ---> {} :: {} --- introduced by: {}, uplinked to: {}'.format(s2.sid, s2, s2.introducedBy, s2.uplink))
                            displayed.append(s2)
                            ### Let's see if there are more servers uplinked.
                            for s3 in [s3 for s3 in localServer.servers if s3 != s2 and s3.uplink and s3.uplink == s2]:
                                self.sendraw(210, ':                                    ---> {} :: {} --- introduced by: {}, uplinked to: {}'.format(s3.sid, s3, s3.introducedBy, s3.uplink))
                                displayed.append(s3)

            self.sendraw(210, ':Total channels in local server.channels list: {}'.format(len(localServer.channels)))
            for c in localServer.channels:
                self.sendraw(210, ':{} {} +{} :: {}'.format(c, c.creation, c.modes, c.topic))
                for u in c.users:
                    self.sendraw(210, ':        {} +{}'.format(u, c.usermodes[u]))

            if 'ulines' in localServer.conf['settings'] and localServer.conf['settings']['ulines']:
                self.sendraw(210, ':Ulines: {}'.format(','.join(localServer.conf['settings']['ulines'])))

            if 'services' in localServer.conf['settings'] and localServer.conf['settings']['services']:
                self.sendraw(210, ':Services: {}'.format(localServer.conf['settings']['services']))

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
                    self.sendraw(243, ':{} {} * {} - {}'.format(recv[1], operhost, oper, localServer.conf['opers'][oper]['operclass']))

        elif recv[1] == 'u':
            uptime = datetime.timedelta(seconds=int(time.time()) - localServer.creationtime)
            self.sendraw(242, ':Server up: {}'.format(uptime))
            try:
                pid = os.getpid()
                py = psutil.Process(pid)
                memoryUse = float(py.memory_info()[0] /2.**20)
                memoryUse = "%.2f" % memoryUse
                self.sendraw(242, ':RAM usage: {} MB'.format(memoryUse))
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
