"""
message-tags capability
"""

from handle.core import Isupport, Numeric, IRCD, Flag, Command, Capability
from handle.logger import logging

HEADER = {
    "name": "message-tags",
    "version": "1",
}


def cmd_tagmsg(client, recv):
    if not client.recv_mtags:
        return
    logging.debug(f"TAGMSG from {client.name}: {recv}")
    target = recv[1]
    prefix = ''
    if target[0] in ''.join([m.prefix for m in IRCD.channel_modes() if m.type == m.MEMBER]):
        prefix = target[0]
        target = target[1:]

    if target[0] in IRCD.CHANPREFIXES:
        if target := IRCD.find_channel(target):
            broadcast = [c for c in target.clients(client_cap="message-tags", prefix=prefix) if c != client]
        else:
            return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv[1])
    else:
        if target := IRCD.find_user(target):
            if target == client and not client.has_capability("echo-message") or not client.has_capability("message-tags"):
                return
            broadcast = [target]
        else:
            return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    """ Add client-tags to .mtags list. """
    mtags = client.recv_mtags
    for tag in client.mtags:
        if tag.name not in [mtag.name for mtag in mtags]:
            mtags.append(tag)
    client.mtags = mtags

    data = f":{client.fullmask} TAGMSG {recv[1]}"
    for user in broadcast:
        user.send(client.mtags, data)

    data = f":{client.id} TAGMSG {recv[1]}"
    IRCD.send_to_servers(client, client.mtags, data)


def init(module):
    Capability.add("message-tags")
    Command.add(module, cmd_tagmsg, "TAGMSG", 1, Flag.CMD_USER, Flag.CMD_SERVER)
    Isupport.add("MTAGS", server_isupport=1)
