"""
/user command
"""

from handle.core import IRCD, Flag, Numeric, Command


def cmd_user(client, recv):
    if client.handshake_finished():
        return client.sendnumeric(Numeric.ERR_ALREADYREGISTRED)

    if client.server:
        return client.exit(f"This port is for servers only.")

    if 'nmap' in ''.join(recv).lower():
        return client.exit("Connection reset by peer")

    ident = str(recv[1][:12]).strip()
    realname = ' '.join(recv[4:]).removeprefix(':')[:48]

    for c in ident:
        if c.lower() not in IRCD.HOSTCHARS:
            ident = ident.replace(c, '')

    if ident and realname:
        client.user.username = ident
        client.info = realname

        if client.handshake_finished():
            client.register_user()


def init(module):
    Command.add(module, cmd_user, "USER", 4, Flag.CMD_USER, Flag.CMD_UNKNOWN, Flag.CMD_SERVER)
