"""
/map and /links command
"""

import datetime
import time

from handle.core import IRCD, Command, Numeric, Isupport, Flag


def cmd_map(client, recv):
    """
    Displays a detailed overview of all linked servers.
    """

    if not client.has_permission("server:info:map"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    current_time = int(time.time())
    for s in [IRCD.me] + [s for s in IRCD.get_clients(server=1) if s.id]:
        percentage = round(100 * (usercount := sum(c.uplink == s for c in IRCD.get_clients(user=1))) / IRCD.global_user_count, 2)
        uptime = datetime.timedelta(seconds=current_time - s.creationtime)
        client.sendnumeric(Numeric.RPL_MAP, f"{s.name} ({s.id})", usercount, percentage, uptime, round(s.lag, 2))
    client.sendnumeric(Numeric.RPL_MAPEND)


def cmd_links(client, recv):
    """
    Displays an overview of all linked servers.
    """

    if not client.has_permission("server:info:links"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    for s in IRCD.get_clients(server=1):
        client.sendnumeric(Numeric.RPL_LINKS, s.name, s.direction.name, s.hopcount, s.info)
    client.sendnumeric(Numeric.RPL_ENDOFLINKS)


def init(module):
    Command.add(module, cmd_map, "MAP", 0, Flag.CMD_OPER)
    Command.add(module, cmd_links, "LINKS", 0, Flag.CMD_OPER)
    Isupport.add("MAP")
