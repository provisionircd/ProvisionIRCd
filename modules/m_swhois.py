"""
/swhois command (server)
"""

from handle.core import IRCD, Command, Flag


def cmd_swhois(client, recv):
    # :001 SWHOIS <nickname> + <tag> :[swhois]
    if not (target_client := IRCD.find_client(recv[1], user=1)):
        return

    if len(recv) < 5:
        # :001 SWHOIS <client_id> -
        # Clear SWHOIS.
        target_client.user.swhois = []
        IRCD.send_to_servers(client, [], recv)
        return

    line = ' '.join(recv[4:]).removeprefix(':')

    if recv[2] == '-':
        target_client.del_swhois(line)

    elif recv[2] == '+':
        target_client.add_swhois(line, tag=recv[3])

    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_swhois, "SWHOIS", 2, Flag.CMD_SERVER)
