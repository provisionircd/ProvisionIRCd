"""
/chgname command
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_chgname(client, recv):
    """
    Changes a users' real nane (GECOS).
    Syntax: CHGNAME <user> <new real name>
    """
    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])
    gecos = ' '.join(recv[2:])[:48].removeprefix(':')
    if gecos == target.info or not gecos:
        return
    target.setinfo(gecos, t='gecos')
    IRCD.send_snomask(client, 's', f'*** {client.name} ({client.user.username}@{client.user.realhost}) used CHGNAME to change the GECOS of {target.name} to "{target.info}"')
    data = f":{client.id} CHGNAME {target.id} :{target.info}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_chgname, "CHGNAME", 2, Flag.CMD_OPER)
