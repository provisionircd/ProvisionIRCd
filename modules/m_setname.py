"""
/setname command
"""

from handle.core import IRCD, Command, Isupport, Capability
from handle.logger import logging

NAMELEN = 50


def cmd_setname(client, recv):
    """
    Changes your own 'real name' (GECOS)
    Syntax:     SETNAME <real name>
    """
    realname = ' '.join(recv[1:])[:NAMELEN].rstrip().removeprefix(':')
    if realname and realname != client.info:
        client.setinfo(realname, t='gecos')
        if client.local:
            IRCD.server_notice(client, f"Your 'real name' has now been changed to: {client.info}")
    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_setname, "SETNAME", 1)
    Isupport.add("NAMELEN", NAMELEN)
    Capability.add("setname")
