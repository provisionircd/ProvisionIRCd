"""
message-tags capability
"""

from handle.core import Isupport, Numeric, IRCD, Flag, Command, Capability

HEADER = dict(name="message-tags", version='1')


def cmd_tagmsg(client, recv):
    if not client.recv_mtags or len(recv[1]) < 2:
        return

    recv_target = recv[1]
    prefix = ''
    if recv_target[0] in IRCD.get_member_prefix_str_sorted():
        prefix = recv_target[0]
        recv_target = recv_target[1:]

    if recv_target[0] in IRCD.CHANPREFIXES + IRCD.get_member_prefix_str_sorted():
        if not (target := IRCD.find_channel(recv_target)):
            return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv_target)
        broadcast = [c for c in target.clients(client_cap="message-tags", prefix=prefix) if c != client]
    else:
        if not (target := IRCD.find_user(recv_target)):
            return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv_target)
        if target == client and not client.has_capability("echo-message") or not client.has_capability("message-tags"):
            return
        broadcast = [target]

    """ Add client-tags to .mtags list. """
    mtags = client.recv_mtags
    existing_names = {mtag.name for mtag in mtags}
    mtags.extend(tag for tag in client.mtags if tag.name not in existing_names)
    client.mtags = mtags

    for user in broadcast:
        user.send(client.mtags, f":{client.fullmask} TAGMSG {target.name}")

    IRCD.send_to_servers(client, client.mtags, f":{client.id} TAGMSG {target.name}")


def init(module):
    Capability.add("message-tags")
    Command.add(module, cmd_tagmsg, "TAGMSG", 1, Flag.CMD_USER, Flag.CMD_SERVER)
    Isupport.add("MTAGS", server_isupport=1)
