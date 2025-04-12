"""
/wallops command
"""

from handle.core import IRCD, Usermode, Command, Flag


def cmd_wallops(client, recv):
    msg = ' '.join(recv[1:]).removeprefix(':')
    for user_client in IRCD.get_clients(local=1, user=1, usermodes='w'):
        user_client.send([], f":{client.fullmask} WALLOPS :{msg}")

    IRCD.send_to_servers(client, [], f":{client.id} WALLOPS :{msg}")


def init(module):
    Usermode.add(module, 'w', 1, 0, Usermode.allow_all, "Can see wallops messages")
    Command.add(module, cmd_wallops, "WALLOPS", 1, Flag.CMD_OPER)
