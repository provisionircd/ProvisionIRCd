"""
/away command
"""

from time import time

from handle.core import Isupport, Command, Numeric, Flag, IRCD, Capability, Hook

AWAYLEN = 300


def cmd_away(client, recv):
    if len(recv) < 2:
        if not client.user.away:
            return

        client.user.away = ''
        client.user.away_since = 0
        client.sendnumeric(Numeric.RPL_UNAWAY)

    else:
        away = ' '.join(recv[1:])[:AWAYLEN].removeprefix(':')

        for result, callback in Hook.call(Hook.PRE_AWAY, args=(client, away)):
            if result == Hook.DENY:
                return

        if away == client.user.away:
            return

        client.user.away = away
        client.user.away_since = int(time())
        client.sendnumeric(Numeric.RPL_NOWAWAY)

    IRCD.new_message(client)
    chan_data = f":{client.fullmask} AWAY {':' + client.user.away if client.user.away else ''}"
    IRCD.send_to_local_common_chans(client=client, mtags=client.mtags, client_cap="away-notify", data=chan_data)

    server_data = f":{client.id} AWAY {':' + client.user.away if client.user.away else ''}"
    IRCD.send_to_servers(client, mtags=client.mtags, data=server_data)

    IRCD.run_hook(Hook.AWAY, client, client.user.away)


def init(module):
    Command.add(module, cmd_away, "AWAY", 0, Flag.CMD_USER)
    Isupport.add("AWAYLEN", AWAYLEN)
    Capability.add("away-notify")
