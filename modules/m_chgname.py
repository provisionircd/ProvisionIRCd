"""
/chgname command
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_chgname(client, recv):
    """
    Changes a users' real nane (GECOS).
    Syntax: CHGNAME <user> <new real name>
    """

    permission_parent = "chgcmds:chgname"

    if not client.has_permission(f"{permission_parent}:local") and not client.has_permission(f"{permission_parent}:global"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if not (target := IRCD.find_client(recv[1], user=1)):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    if client.local:
        permission_check = f"{permission_parent}:global" if not target.local else f"{permission_parent}:local"
        if not client.has_permission(permission_check) and not client.has_permission(f"{permission_parent}:global"):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    gecos = ' '.join(recv[2:])[:50].removeprefix(':').strip()
    if gecos == target.info or not gecos:
        return

    target.setinfo(gecos, change_type="gecos")
    IRCD.send_snomask(client, 's', f"*** {client.name} ({client.user.username}@{client.user.realhost}) "
                                   f"used CHGNAME to change the GECOS of {target.name} to \"{target.info}\"")

    IRCD.send_to_servers(client, [], data=f":{client.id} CHGNAME {target.id} :{target.info}")


def init(module):
    Command.add(module, cmd_chgname, "CHGNAME", 2, Flag.CMD_OPER)
