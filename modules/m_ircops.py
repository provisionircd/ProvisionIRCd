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
        client.sendraw(self.RPL.IRCOPS, ':Nick                  Status             Server')
        client.sendraw(self.RPL.IRCOPS, ':------------------------------------------')
        aways, opers = 0, 0
        for oper in [u for u in self.ircd.users if 'o' in u.modes and ('H' not in u.modes or 'o' in client.modes) and 'S' not in u.modes]:
            opers += 1
            status = ''
            if oper.away:
                aways += 1
                status += '(AWAY)'
            if 'H' in oper.modes:
                status += '{}(+H)'.format(' ' if oper.away else '')
            nick_len = len(oper.nickname[23:])
            s = oper.server.hostname.rjust(33-(len(status))-nick_len)
            client.sendraw(self.RPL.IRCOPS, f':{oper.nickname:22}Oper {status} {s}')
        client.sendraw(self.RPL.IRCOPS, ':Total: {} IRCOP{} connected - {} Away'.format(opers, 's' if opers != 1 else '', aways))
        client.sendraw(self.RPL.IRCOPS, ':§~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~~¤§¤~§')
        client.sendraw(self.RPL.ENDOFIRCOPS, ':End of /IRCOPS.')
