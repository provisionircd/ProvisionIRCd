"""
/ircops command (show online opers)
"""

from handle.core import IRCD, Numeric, Command


def cmd_ircops(client, recv):
    """
    Displays all online IRC Operators.
    """

    header_divider = "§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§"
    client.sendnumeric(Numeric.RPL_IRCOPS, header_divider)
    client.sendnumeric(Numeric.RPL_IRCOPS, "Nick                    Status           Server")
    client.sendnumeric(Numeric.RPL_IRCOPS, "-----------------------------------------------")

    aways = opers = 0
    for oper_client in (c for c in IRCD.get_clients(user=1, usermodes='o')
                        if (('H' not in c.user.modes or 'o' in client.user.modes)
                            and 'S' not in c.user.modes)):
        opers += 1
        status = ''

        if oper_client.user.away:
            aways += 1
            status += "(AWAY)"

        if 'H' in oper_client.user.modes:
            status += f"{' ' if oper_client.user.away else ''}(+H)"
        nick_len = len(oper_client.name[24:])
        width = 31 - len(status) - nick_len
        client.sendnumeric(Numeric.RPL_IRCOPS, f"{oper_client.name:23} Oper {status} {oper_client.uplink.name:>{width}}")

    client.sendnumeric(Numeric.RPL_IRCOPS, f"Total: {opers} IRCOP{'s' if opers != 1 else ''} connected - {aways} Away")
    client.sendnumeric(Numeric.RPL_IRCOPS, header_divider)
    client.sendnumeric(Numeric.RPL_ENDOFIRCOPS)


def init(module):
    Command.add(module, cmd_ircops, "IRCOPS")
