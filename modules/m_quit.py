"""
/quit command
"""

import ircd


@ircd.Modules.command
class Quit(ircd.Command):
    """
    Disconnect from the network.
    Syntax: QUIT [reason]
    """

    def __init__(self):
        self.command = 'quit'

    def execute(self, client, recv, showPrefix=True):
        source = None
        if type(client).__name__ == 'Server':
            source = client
            showPrefix = False
            if not client.eos:
                return
            client = list(filter(lambda u: u.uid == recv[0][1:], self.ircd.users))
            if not client:
                ### User is already disconnected.
                return
            else:
                client = client[0]

            recv = recv[1:]

        if len(recv) > 1:
            reason = ' '.join(recv[1:][:128])
            if reason.startswith(':'):
                reason = reason[1:]
        else:
            reason = client.nickname

        try:
            quitprefix = str(self.ircd.conf['settings']['quitprefix']).strip()

            if quitprefix.endswith(':'):
                quitprefix = quitprefix[:-1]
        except:
            quitprefix = 'Quit'

        if 'static-quit' in self.ircd.conf['settings'] and self.ircd.conf['settings']['static-quit']:
            reason = self.ircd.conf['settings']['static-quit']

        reason = '{}{}'.format(quitprefix + ': ' if client.server == self.ircd and showPrefix else '', reason)
        client.quit(reason, error=False)
