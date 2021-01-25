"""
/stats command
"""

import datetime
import os
import sys
import time

import ircd

try:
    import psutil
except ImportError:
    pass

stats = 'deglpuCGLO'


class Stats(ircd.Command):
    """
    View several server stats.
    """

    def __init__(self):
        self.command = 'stats'
        self.req_modes = 'o'
        self.req_flags = 'stats'

    def execute(self, client, recv):
        if len(recv) == 1:
            client.sendraw(210, ':/Stats flags:')
            client.sendraw(210, ':d - Displays the local DNSBL cache')
            client.sendraw(210, ':e - View exceptions list')
            client.sendraw(210, ':g - View the local TKL info')
            client.sendraw(210, ':l - View link information')
            client.sendraw(210, ':p - View open ports and their type')
            client.sendraw(210, ':u - View server uptime')
            client.sendraw(210, ':C - View raw server data and info')
            client.sendraw(210, ':G - View the global TKL info')
            client.sendraw(210, ':L - View link all information, including unlinked')
            client.sendraw(210, ':O - Send the oper block list')
            return client.sendraw(219, '* :End of /STATS report')

        elif recv[1] not in stats:
            return client._send(':{} NOTICE {} :* STATS -- Unknown stats "{}"'.format(self.ircd.hostname, client.uid, recv[1]))

        if recv[1] == 'C':
            client.sendraw(210, ':{} socket: {}'.format(self.ircd, self.ircd.socket))
            client.sendraw(210, ':Total connected users in local server.users list: {}'.format(len(self.ircd.users)))
            for u in self.ircd.users:
                hopcount = 0 if u.server == self.ircd else u.server.hopcount
                client.sendraw(210, ':            {} ({}) :: refcount: {}, class: {}, hopcount: {}'.format(u, u.ip, sys.getrefcount(u), u.cls if u.server == self.ircd else 'remote user', hopcount))
            client.sendraw(210, ':Total connected servers in local server.servers list (not including local): {}'.format(len(self.ircd.servers)))
            displayed = []
            for s in self.ircd.servers:
                if s.sid:
                    if s.socket:
                        client.sendraw(210, ':            {} {} :: {} --- socket: {}, class: {}, eos: {}'.format(s.sid, s.hostname, s, s.socket, s.cls, s.eos))
                    for s2 in self.ircd.servers:
                        if s2.introducedBy == s and s2 not in displayed:
                            client.sendraw(210, ':                        ---> {} :: {} --- introduced by: {}, uplinked to: {}'.format(s2.sid, s2, s2.introducedBy, s2.uplink))
                            displayed.append(s2)
                            ### Let's see if there are more servers uplinked.
                            for s3 in [s3 for s3 in self.ircd.servers if s3 != s2 and s3.uplink and s3.uplink == s2]:
                                client.sendraw(210, ':                                    ---> {} :: {} --- introduced by: {}, uplinked to: {}'.format(s3.sid, s3, s3.introducedBy, s3.uplink))
                                displayed.append(s3)

            client.sendraw(210, ':Total channels in local server.channels list: {}'.format(len(self.ircd.channels)))
            for c in self.ircd.channels:
                client.sendraw(210, ':{} {} +{} :: {}'.format(c, c.creation, c.modes, c.topic))
                for u in c.users:
                    client.sendraw(210, ':        {} +{}'.format(u, c.usermodes[u]))

            if 'ulines' in self.ircd.conf['settings'] and self.ircd.conf['settings']['ulines']:
                client.sendraw(210, ':Ulines: {}'.format(','.join(self.ircd.conf['settings']['ulines'])))

            if 'services' in self.ircd.conf['settings'] and self.ircd.conf['settings']['services']:
                client.sendraw(210, ':Services: {}'.format(self.ircd.conf['settings']['services']))

        elif recv[1] == 'd':
            total_len = len(self.ircd.dnsblCache)
            dnsbl = self.ircd.dnsblCache if len(self.ircd.dnsblCache) < 128 else sorted(self.ircd.dnsblCache)[:128]
            for entry in dnsbl:
                t = self.ircd.dnsblCache[entry]
                date = '{} {}'.format(datetime.datetime.fromtimestamp(float(t['ctime'])).strftime('%a %b %d %Y'), datetime.datetime.fromtimestamp(float(t['ctime'])).strftime('%H:%M:%S %Z'))
                date = date.strip()
                client.sendraw(210, ':{} {} {}'.format(entry, self.ircd.dnsblCache[entry]['bl'], date))
            if len(dnsbl) == 128:
                client.sendraw(210, ':Showing only first 128 entries. Total entries: {}'.format(total_len))

        elif recv[1] == 'e':
            for t in self.ircd.excepts:
                for mask in self.ircd.excepts[t]:
                    client.sendraw(223, '{} {}'.format(t, mask))

        elif recv[1] == 'g':
            for type in [type for type in self.ircd.tkl if type in 'gz']:
                for mask in self.ircd.tkl[type]:
                    display = mask.split('@')[1] if type == 'Q' else mask
                    t = self.ircd.tkl[type][mask]
                    client.sendraw(223, '{} {} {} {} {} :{}'.format(type, display, int(t['expire']) - int(time.time()) if t['expire'] != '0' else '0', t['ctime'], t['setter'], t['reason']))

        elif recv[1] in 'lL':
            for link in self.ircd.conf['link']:
                t = self.ircd.conf['link'][link]
                name = link
                if recv[1] == 'l' and not [s for s in self.ircd.servers if s.hostname == name]:
                    continue
                link_class = t['class']
                incoming_host = t['incoming']['host']
                outgoing_host, outgoing_port = None, None
                if 'outgoing' in t:
                    if 'host' in t['outgoing']:
                        outgoing_host = t['outgoing']['host']
                    if 'port' in t['outgoing']:
                        outgoing_port = t['outgoing']['port']
                client.sendraw(210, '{} :{} >{} {{{}}}'.format(recv[1], link, incoming_host, link_class))


        elif recv[1] == 'p':
            for sock in self.ircd.listen_socks:
                ip, port = sock.getsockname()
                options = ', '.join(self.ircd.conf['listen'][str(port)]['options'])
                total_clients = [s for s in self.ircd.users + self.ircd.servers if s.socket]
                port_clients = [client for client in total_clients if (client.socket.getsockname()[1] == port or client.socket.getpeername()[1] == port)]
                client.sendraw(210, '{} {}:{} [options: {}], used by {} client{}'.format(recv[1], ip, port, options, len(port_clients), 's' if len(port_clients) != 1 else ''))

        elif recv[1] == 'G':
            for type in [type for type in self.ircd.tkl if type in 'gGZQ']:  # G should also see g (local)
                for mask in self.ircd.tkl[type]:
                    display = mask.split('@')[1] if type == 'Q' else mask
                    t = self.ircd.tkl[type][mask]
                    client.sendraw(223, '{} {} {} {} {} :{}'.format(type, display, int(t['expire']) - int(time.time()) if t['expire'] != '0' else '0', t['ctime'], t['setter'], t['reason']))

        elif recv[1] == 'O':
            for oper in self.ircd.conf['opers']:
                for operhost in self.ircd.conf['opers'][oper]['host']:
                    client.sendraw(243, ':{} {} * {} - {}'.format(recv[1], operhost, oper, self.ircd.conf['opers'][oper]['operclass']))

        elif recv[1] == 'u':
            uptime = datetime.timedelta(seconds=int(time.time()) - self.ircd.creationtime)
            client.sendraw(242, ':Server up: {}'.format(uptime))
            try:
                pid = os.getpid()
                py = psutil.Process(pid)
                memoryUse = float(py.memory_info()[0] / 2. ** 20)
                memoryUse = "%.2f" % memoryUse
                client.sendraw(242, ':RAM usage: {} MB'.format(memoryUse))
            except:
                pass

        client.sendraw(219, '{} :End of /STATS'.format(recv[1]))
        msg = '* Stats "{}" requested by {} ({}@{})'.format(recv[1], client.nickname, client.ident, client.hostname)
        self.ircd.snotice('s', msg)
