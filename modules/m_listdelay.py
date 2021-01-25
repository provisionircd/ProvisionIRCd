"""
blocks /list commands for newly connected users
"""

import time

import ircd

delay = 60


@ircd.Modules.hooks.pre_command('list')
def delaylist(client, localServer, recv):
    if int(time.time()) - client.signon < delay and 'o' not in client.modes:
        localServer.notice(client, '*** Please wait a while before requesting channel list.')
        client.sendraw(321, 'Channel :Users  Name')
        client.sendraw(323, ':End of /LIST')
        return 0
