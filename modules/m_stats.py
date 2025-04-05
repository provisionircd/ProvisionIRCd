"""
/stats command
"""

import datetime
import os
import sys
import time
import typing

try:
    # noinspection PyPackageRequirements
    import psutil
except ImportError:
    psutil = None

from handle.core import IRCD, Command, Stat, Numeric, Flag
from modules.m_tkl import Tkl

from handle.logger import logging


def cmd_stats(client, recv):
    """
    View several server stats.
    Use STATS for available flags.
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


def stats_exception(client):
    for e in IRCD.configuration.excepts:
        for mask in e.mask:
            client.sendnumeric(Numeric.RPL_STATSEXCEPTTKL, e.name, ' '.join(mask), e.set_time, e.expire, e.comment)
    for tkl in [tkl for tkl in Tkl.table if tkl.type == 'e']:
        client.sendnumeric(Numeric.RPL_STATSEXCEPTTKL, tkl.bantypes, tkl.mask, tkl.set_time, tkl.expire, tkl.reason)


def stats_links(client):
    links = [s for s in IRCD.get_clients(local=1, server=1) if s != IRCD.me]
    client.sendnumeric(Numeric.RPL_STATSLINKINFO, 'l', "Name", "SendQ", "SendM", "SendBytes", "RcveM", "RcveBytes", "Open_since", "Idle")
    for server in links:
        client.sendnumeric(Numeric.RPL_STATSLINKINFO, 'l', server.name, server.class_.sendq, server.local.messages_sent,
                           server.local.bytes_sent, server.local.messages_received, server.local.bytes_received,
                           int(time.time()) - server.creationtime, int(time.time() - server.idle_since))


def stats_links_all(client):
    links = [s for s in IRCD.get_clients(local=1, server=1) if s != IRCD.me]
    shown_names = [s.name for s in links]
    client.sendnumeric(Numeric.RPL_STATSLINKINFO, 'L', "Name", "SendQ", "SendM", "SendBytes", "RcveM", "RcveBytes", "Open_since", "Idle")
    for server in links:
        client.sendnumeric(Numeric.RPL_STATSLINKINFO, 'L', server.name, server.class_.sendq, server.local.messages_sent,
                           server.local.bytes_sent, server.local.messages_received, server.local.bytes_received,
                           int(time.time()) - server.creationtime, int(time.time() - server.idle_since))
    for link in [link for link in IRCD.configuration.links if link.name not in shown_names]:
        link_class = IRCD.get_class_from_name(link.connectclass)
        client.sendnumeric(Numeric.RPL_STATSLINKINFO, 'L', link.name, link_class.sendq, 0, 0, 0, 0, 0, 0)


def stats_opers(client):
    for oper in IRCD.configuration.opers:
        client.sendnumeric(Numeric.RPL_STATSOLINE, 'O', oper.operhost, oper.name, '-', oper.operclass.name)


def stats_uptime(client):
    uptime = datetime.timedelta(seconds=int(time.time()) - IRCD.me.creationtime)
    client.sendnumeric(Numeric.RPL_STATSUPTIME, f":Server up: {uptime}")
    try:
        psutil_instance: typing.Any = psutil
        if not (proc := psutil_instance.Process(IRCD.pid)):
            return

        pid = os.getpid()

        memory_use = float(proc.memory_info()[0] / 2. ** 20)
        memory_use = "%.2f" % memory_use
        client.sendnumeric(Numeric.RPL_STATSUPTIME, f":RAM usage: {memory_use} MB")

        open_files = proc.open_files()
        open_connections = proc.connections(kind="all")
        client.sendnumeric(Numeric.RPL_STATSUPTIME, f":Open files: {len(open_files) + len(open_connections)}")

        logging.debug(f"========== Open files: ==========")
        for file in open_files:
            logging.debug(f"Open file: {file}")

        logging.debug(f"========== Open connections: ==========")
        for conn in proc.connections(kind="all"):
            logging.debug(f"Type: {conn.type} | Local: {conn.laddr} | Remote: {conn.raddr} | Status: {conn.status}")

    except NameError:
        pass
    except Exception as ex:
        logging.exception(ex)


def stats_debug(client):
    for u in IRCD.get_clients(user=1):
        client.sendnumeric(Numeric.RPL_STATSDEBUG,
                           f"            {u} :: refcount: {sys.getrefcount(u)}")
        client.sendnumeric(Numeric.RPL_STATSDEBUG, '-')
    displayed = []
    for s in IRCD.get_clients(server=1):
        if s.id:
            if s.local:
                client.sendnumeric(Numeric.RPL_STATSDEBUG,
                                   f"            {s.id} {s.name} --- socket: {s.local.socket}, class: {s.class_}, eos: {s.server.synced}")
            for s2 in IRCD.get_clients(server=1):
                if s2.uplink == s and s2 not in displayed:
                    client.sendnumeric(Numeric.RPL_STATSDEBUG,
                                       f"                        ---> {s2.name} :: {s2} --- uplinked to: {s2.uplink.name}")
                    displayed.append(s2)
                    # Let's see if there are more servers uplinked.
                    for s3 in [s3 for s3 in IRCD.get_clients(server=1) if s3 != s2 and s3.uplink == s2]:
                        client.sendnumeric(Numeric.RPL_STATSDEBUG,
                                           f"                                    ---> {s3.sid} --- uplinked to: {s3.uplink.name}")
                        displayed.append(s3)

    for c in IRCD.get_channels():
        client.sendnumeric(Numeric.RPL_STATSDEBUG, f"{c.name} {c.creationtime} +{c.modes} :: {c.topic}")
        for member_client in c.member_by_client:
            client.sendnumeric(Numeric.RPL_STATSDEBUG, f"        {member_client.name} "
                                                       f"{[c.flag for c in c.get_membermodes_sorted(client=member_client)]}")
        client.sendnumeric(Numeric.RPL_STATSDEBUG, '-')

    client_ids = len(IRCD.client_by_id)
    client_names = len(IRCD.client_by_name)
    client.sendnumeric(Numeric.RPL_STATSDEBUG, "----------")
    client.sendnumeric(Numeric.RPL_STATSDEBUG, f"========== Hashed keys ==========")
    client.sendnumeric(Numeric.RPL_STATSDEBUG, f"{'Hashed client IDs:':<25}{client_ids}")
    client.sendnumeric(Numeric.RPL_STATSDEBUG, f"{'Hashed client names:':<25}{client_names}")
    client.sendnumeric(Numeric.RPL_STATSDEBUG, f"{'Hashed sockets:':<25}{len(IRCD.client_by_sock)}")
    client.sendnumeric(Numeric.RPL_STATSDEBUG, '-')
    client.sendnumeric(Numeric.RPL_STATSDEBUG, f"{'Total clients in table:':<25}{len(list(IRCD.get_clients()))}")
    client.sendnumeric(Numeric.RPL_STATSDEBUG, f"{'Local clients in table:':<25}{len(list(IRCD.get_clients(local=1)))}")
    client.sendnumeric(Numeric.RPL_STATSDEBUG, '-')
    client.sendnumeric(Numeric.RPL_STATSDEBUG, f"{'Hashed channel names:':<25}{len(IRCD.channel_by_name)}")
    client.sendnumeric(Numeric.RPL_STATSDEBUG, f"{'Total channels in table:':<25}{len(list(IRCD.get_channels()))}")
    client.sendnumeric(Numeric.RPL_STATSDEBUG, "----------")

    if ulines := IRCD.get_setting("ulines"):
        client.sendnumeric(Numeric.RPL_STATSDEBUG, f"Ulines: {', '.join(ulines)}")

    if services := IRCD.get_setting("services"):
        client.sendnumeric(Numeric.RPL_STATSDEBUG, f"Services: {services}")


def stats_ports(client):
    for listen in IRCD.configuration.listen:
        port_clients = [client for client in IRCD.get_clients(local=1) if
                        (int(client.local.socket.getsockname()[1]) == int(listen.port) or int(client.local.socket.getpeername()[1]) == int(
                            listen.port))]
        listen_string = (f"Listener: {listen.ip}:{listen.port} "
                         f"[options: {', '.join(listen.options) if listen.options else 'None'}], "
                         f"used by {len(port_clients)} client{'s' if len(port_clients) != 1 else ''}")
        IRCD.server_notice(client, listen_string)


def stats_servers(client):
    for server_client in IRCD.get_clients(server=1):
        dt_object = datetime.datetime.fromtimestamp(server_client.creationtime)
        formatted_time = dt_object.strftime("%Y-%m-%d %H:%M:%S")
        time_elapsed = datetime.datetime.now() - dt_object
        days = time_elapsed.days
        hours, remainder = divmod(time_elapsed.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        name = server_client.name
        uplink = server_client.uplink
        synced = server_client.server.synced

        IRCD.server_notice(client, '-')
        stat_string = f"{name} (Uplink: {uplink.name}, direction: {client.direction.name}, synced: {synced})"
        IRCD.server_notice(client, stat_string)
        IRCD.server_notice(client,
                           f"    Connect date: {formatted_time} ({days} days, {hours} hours, {minutes} minutes, {seconds} seconds ago)")
        IRCD.server_notice(client, f"    Last message received: {int(time.time()) - server_client.local.last_msg_received} seconds ago")


def init(module):
    Command.add(module, cmd_stats, "STATS", 0, Flag.CMD_OPER)
    Stat.add(module, stats_exception, 'e', "View exceptions list")
    Stat.add(module, stats_links, 'l', "View link information")
    Stat.add(module, stats_servers, 's', "View info about all connected servers")
    Stat.add(module, stats_links_all, 'L', "View link all information, including unlinked")
    Stat.add(module, stats_opers, 'O', "View oper blocks")
    Stat.add(module, stats_uptime, 'u', "View uptime information")
    Stat.add(module, stats_ports, 'P', "View all open ports and their type")
    Stat.add(module, stats_debug, 'C', "View raw client data")
