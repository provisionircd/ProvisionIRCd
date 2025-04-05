"""
/setname command
"""

from handle.core import IRCD, Command, Isupport, Capability

NAMELEN = 50


def cmd_setname(client, recv):
    """
    Changes your own 'real name' (GECOS)
    Syntax:     SETNAME <real name>
    """

    realname = ' '.join(recv[1:])[:NAMELEN].removeprefix(':').strip()
    if realname.strip() and realname != client.info:
        client.setinfo(realname, change_type="gecos")

    IRCD.send_to_servers(client, [], data=f":{client.id} {' '.join(recv)}")


def init(module):
    Command.add(module, cmd_setname, "SETNAME", 1)
    Isupport.add("NAMELEN", NAMELEN)
    Capability.add("setname")
