"""
/ircops command (show online opers)
"""

import ircd


class Ircops(ircd.Command):
    """
    Displays all online IRC Operators.
    """

    def __init__(self):
        self.command = 'ircops'

    def execute(self, client, recv):
        client.sendraw(self.RPL.IRCOPS, ':§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
        client.sendraw(self.RPL.IRCOPS, ':Nick                  Status         Server')
        client.sendraw(self.RPL.IRCOPS, ':--------------------------------------------')
        aways, opers = 0, 0
        for oper in [user for user in self.ircd.users if 'o' in user.modes and ('H' not in user.modes or 'o' in client.modes) and 'S' not in user.modes]:
            opers += 1
            if oper.away:
                aways += 1
            status = '{0:12}'.format('')
            ph_len = 8
            if oper.away:
                if 'H' in oper.modes:
                    status = '{0:8}'.format(' (AWAY)')
                else:
                    status = '{0:12}'.format(' (AWAY)')
            if 'H' in oper.modes:
                if oper.away:
                    status += '{0:4}'.format('(+H)')
                else:
                    status = '{0:12}'.format(' (+H)')
            client.sendraw(self.RPL.IRCOPS, ':{u.nickname:22}Oper{} {u.server.hostname}'.format(status, u=oper))
        client.sendraw(self.RPL.IRCOPS, ':Total: {} IRCOP{} connected - {} Away'.format(opers, 's' if opers != 1 else '', aways))
        client.sendraw(self.RPL.IRCOPS, ':§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
        client.sendraw(self.RPL.ENDOFIRCOPS, ':End of /IRCOPS.')
