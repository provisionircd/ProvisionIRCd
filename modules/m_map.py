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

    for s in [s for s in IRCD.global_servers() if s.id]:
        usercount = len([c for c in IRCD.global_users() if c.uplink == s])
        percentage = round(100 * float(usercount) / float(IRCD.global_user_count), 2)
        uptime = datetime.timedelta(seconds=int(time.time()) - s.creationtime)
        client.sendnumeric(Numeric.RPL_MAP, s.name + ' (' + s.id + ')', usercount, percentage, uptime, round(s.lag, 2))
    client.sendnumeric(Numeric.RPL_MAPEND)


def cmd_links(client, recv):
    """
    Displays an overview of all linked servers.
    """
    for s in IRCD.global_servers():
        client.sendnumeric(Numeric.RPL_LINKS, s.name, s.direction.name, s.hopcount, s.info)
    client.sendnumeric(Numeric.RPL_ENDOFLINKS)


def init(module):
    Command.add(module, cmd_map, "MAP", 0, Flag.CMD_OPER)
    Command.add(module, cmd_links, "LINKS", 0, Flag.CMD_OPER)
    Isupport.add("MAP")
