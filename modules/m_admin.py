"""
/admin command
"""

from handle.core import IRCD, Numeric, Command


def cmd_admin(client, recv):
    if not (admin_block := IRCD.configuration.get_block("admin")):
        return
    client.sendnumeric(Numeric.RPL_ADMINME, IRCD.me.name)
    for idx, entry in enumerate(admin_block.entries):
        match idx:
            case 0:
                rpl = Numeric.RPL_ADMINLOC1
            case 1:
                rpl = Numeric.RPL_ADMINLOC2
            case _:
                rpl = Numeric.RPL_ADMINEMAIL
        client.sendnumeric(rpl, entry.get_single_value())


def init(module):
    Command.add(module, cmd_admin, "ADMIN")
