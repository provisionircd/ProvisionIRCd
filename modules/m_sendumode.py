"""
/sendumode command (server)
"""

from handle.core import IRCD, Command, Flag


def cmd_sendumode(client, recv):
    # :00B SENDUMODE o :message
    for user_client in IRCD.get_clients(local=1, user=1, usermodes=recv[1]):
        IRCD.server_notice(user_client, ' '.join(recv[2:]).removeprefix(':'))
    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def cmd_sendsno(client, recv):
    flag = recv[1]
    message = ' '.join(recv[2:]).removeprefix(':')
    IRCD.send_snomask(client, flag, message)


def init(module):
    Command.add(module, cmd_sendsno, "SENDSNO", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_sendumode, "SENDUMODE", 2, Flag.CMD_SERVER)
