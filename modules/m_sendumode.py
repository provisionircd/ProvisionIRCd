"""
/sendumode command (server)
"""

from handle.core import IRCD, Command, Flag


def cmd_sendumode(client, recv):
    # :00B SENDUMODE o :message
    for user_client in IRCD.get_clients(local=1, user=1, usermodes=recv[1]):
        Command.do(client, "NOTICE", user_client.name, *recv[2:])

    IRCD.send_to_servers(client, [], f":{client.id} {' '.join(recv)}")


def cmd_sendsno(client, recv):
    flag = recv[1]
    message = ' '.join(recv[2:]).removeprefix(':')
    IRCD.send_snomask(client, flag, message)


def init(module):
    Command.add(module, cmd_sendsno, "SENDSNO", 2, Flag.CMD_SERVER)
    Command.add(module, cmd_sendumode, "SENDUMODE", 2, Flag.CMD_SERVER)
