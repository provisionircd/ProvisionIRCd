"""
/stats command
"""

import datetime
import os
import sys
import time

from handle.core import IRCD, Command, Stat, Numeric, Flag, Tkl
from handle.logger import logging

try:
    import psutil
except ImportError:
    pass


def cmd_stats(client, recv):
    """
    View several server stats.
    """
    if not client.has_permission("server:info:stats"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if len(recv) == 1:
        stats_sorted = sorted([stat for stat in Stat.table], key=lambda s: s.letter, reverse=True)
        client.sendnumeric(Numeric.RPL_STATSHELP, '*', "/Stats flags:")
        for stat in stats_sorted:
            client.sendnumeric(Numeric.RPL_STATSHELP, stat.letter, stat.desc)
        return client.sendnumeric(Numeric.RPL_ENDOFSTATS, '*')

    if not (stat := Stat.get(recv[1])):
        return IRCD.server_notice(client, f"* STATS -- Unknown stats '{recv[1]}'")

    stat.show(client)

    # DNSBL for future module.
    # if recv[1] == 'd':
    #     total_len = len(Internal.dnsblCache)
    #     dnsbl = Internal.dnsblCache if len(Internal.dnsblCache) < 128 else sorted(Internal.dnsblCache)[:128]
    #     for entry in dnsbl:
    #         t = Internal.dnsblCache[entry]
    #         date = f'{datetime.datetime.fromtimestamp(float(t["ctime"])).strftime("%a %b %d %Y")} {datetime.datetime.fromtimestamp(float(t["ctime"])).strftime("%H:%M:%S %Z")}'
    #         date = date.strip()
    #         client.sendraw(210, f':{entry} {Internal.dnsblCache[entry]["bl"]} {date}')
    #     if len(dnsbl) == 128:
    #         client.sendraw(210, f':Showing only first 128 entries. Total entries: {total_len}')


def stats_exception(client):
    for e in IRCD.configuration.excepts:
        for mask in e.mask:
            client.sendnumeric(Numeric.RPL_STATSEXCEPTTKL, e.name, ' '.join(mask), e.set_time, e.expire, e.comment)
    for tkl in [tkl for tkl in Tkl.table if tkl.type == 'e']:
        client.sendnumeric(Numeric.RPL_STATSEXCEPTTKL, tkl.bantypes, tkl.mask, tkl.set_time, tkl.expire, tkl.reason)


def stats_links(client):
    links = [s for s in IRCD.local_servers() if s != IRCD.me]
    client.sendnumeric(Numeric.RPL_STATSLINKINFO, "l", "Name", "SendQ", "SendM", "SendBytes", "RcveM", "RcveBytes", "Open_since", "Idle")
    for server in links:
        client.sendnumeric(Numeric.RPL_STATSLINKINFO, "l", server.name, server.class_.sendq, server.local.messages_sent,
                           server.local.bytes_sent, server.local.messages_received, server.local.bytes_received,
                           int(time.time()) - server.creationtime, int(time.time() - server.idle_since))


def stats_links_all(client):
    links = [s for s in IRCD.local_servers() if s != IRCD.me]
    shown_names = [s.name for s in links]
    client.sendnumeric(Numeric.RPL_STATSLINKINFO, "L", "Name", "SendQ", "SendM", "SendBytes", "RcveM", "RcveBytes", "Open_since", "Idle")
    for server in links:
        client.sendnumeric(Numeric.RPL_STATSLINKINFO, "L", server.name, server.class_.sendq, server.local.messages_sent,
                           server.local.bytes_sent, server.local.messages_received, server.local.bytes_received,
                           int(time.time()) - server.creationtime, int(time.time() - server.idle_since))
    for link in [link for link in IRCD.configuration.links if link.name not in shown_names]:
        link_class = IRCD.get_class_from_name(link.connectclass)
        client.sendnumeric(Numeric.RPL_STATSLINKINFO, "L", link.name, link_class.sendq, 0, 0, 0, 0, 0, 0)


def stats_opers(client):
    for oper in IRCD.configuration.opers:
        client.sendnumeric(Numeric.RPL_STATSOLINE, "O", oper.operhost, oper.name, '-', oper.operclass.name)


def stats_uptime(client):
    uptime = datetime.timedelta(seconds=int(time.time()) - IRCD.boottime)
    client.sendnumeric(Numeric.RPL_STATSUPTIME, f":Server up: {uptime}")
    try:
        pid = os.getpid()
        py = psutil.Process(pid)
        memory_use = float(py.memory_info()[0] / 2. ** 20)
        memory_use = "%.2f" % memory_use
        client.sendnumeric(Numeric.RPL_STATSUPTIME, f":RAM usage: {memory_use} MB")
    except:
        pass


def stats_debug(client):
    for u in IRCD.global_users():
        client.sendnumeric(Numeric.RPL_STATSDEBUG,
                           f'            {u} :: refcount: {sys.getrefcount(u)}')
    displayed = []
    for s in IRCD.global_servers():
        if s.id:
            if s.local:
                client.sendnumeric(Numeric.RPL_STATSDEBUG, f'            {s.id} {s.name} --- socket: {s.local.socket}, class: {s.class_}, eos: {s.server.synced}')
            for s2 in IRCD.global_servers():
                if s2.uplink == s and s2 not in displayed:
                    client.sendnumeric(Numeric.RPL_STATSDEBUG, f'                        ---> {s2.name} :: {s2} --- uplinked to: {s2.uplink.name}')
                    displayed.append(s2)
                    # Let's see if there are more servers uplinked.
                    for s3 in [s3 for s3 in IRCD.global_servers() if s3 != s2 and s3.uplink == s2]:
                        client.sendnumeric(Numeric.RPL_STATSDEBUG, f'                                    ---> {s3.sid} --- uplinked to: {s3.uplink.name}')
                        displayed.append(s3)

    for c in IRCD.get_channels():
        client.sendnumeric(Numeric.RPL_STATSDEBUG, f'{c.name} {c.creationtime} +{c.modes} :: {c.topic}')
        for m in c.members:
            client.sendnumeric(Numeric.RPL_STATSDEBUG, f'        {m.client.name} +{c.get_modes_of_client_str(m.client)}')

    if ulines := IRCD.get_setting("ulines"):
        client.sendnumeric(Numeric.RPL_STATSDEBUG, f'Ulines: {", ".join(ulines)}')

    if services := IRCD.get_setting("services"):
        client.sendnumeric(Numeric.RPL_STATSDEBUG, f'Services: {services}')


def stats_ports(client):
    for listen in IRCD.configuration.listen:
        port_clients = [client for client in IRCD.local_clients() if
                        (int(client.local.socket.getsockname()[1]) == int(listen.port) or int(client.local.socket.getpeername()[1]) == int(listen.port))]
        listen_string = f"Listener: {listen.ip}:{listen.port}" \
                        f"[options: {', '.join(listen.options) if listen.options else 'None'}], " \
                        f"used by {len(port_clients)} client{'s' if len(port_clients) != 1 else ''}"
        IRCD.server_notice(client, listen_string)
        # client.sendnumeric(Numeric.RPL_INFO, f"P {listen.ip}:{listen.port}"
        #                                     f"[options: {', '.join(listen.options) if listen.options else 'None'}], "
        #                                     f"used by {len(port_clients)} client{'s' if len(port_clients) != 1 else ''}")


def init(module):
    Command.add(module, cmd_stats, "STATS", 0, Flag.CMD_OPER)
    Stat.add(module, stats_exception, "e", "View exceptions list")
    Stat.add(module, stats_links, "l", "View link information")
    Stat.add(module, stats_links_all, "L", "View link all information, including unlinked")
    Stat.add(module, stats_opers, "O", "View oper blocks")
    Stat.add(module, stats_uptime, "u", "View uptime information")
    Stat.add(module, stats_ports, "P", "View all open ports and their type")
    Stat.add(module, stats_debug, "C", "View raw client data")
