"""
ping/pong handler
"""

from time import time
from handle.core import IRCD, Command, Flag
from handle.logger import logging


@logging.client_context
def cmd_ping(client, recv):
    """
    Send a PING message to keep the connection alive.
    """
    if client.server:
        if not (ping_from := IRCD.find_client(recv[1])):
            logging.error(f"Ping from unknown server: {recv[1]}")
            return

        if len(recv) < 3:
            logging.error(f"Malformed PING received from server {recv[1]}: missing destination")
            return

        if not (ping_to := IRCD.find_client(recv[2])):
            logging.error(f"Server {ping_from.name} tries to ping unknown server: {recv[2]}")
            return

        client.send([], f":{ping_to.id} PONG {ping_to.name} {ping_from.name}")
        return

    response = recv[1].removeprefix(':')
    client.send([], f":{IRCD.me.name} PONG {IRCD.me.name} :{response}")


def cmd_nospoof(client, reply):
    if reply == client.local.nospoof:
        client.local.nospoof = 0
    elif client.local.nospoof:
        IRCD.server_notice(client, f"ERROR: Invalid PING response. Your client must respond back with PONG {client.local.nospoof}")


def cmd_pong(client, recv):
    """
    Reply to a PING command.
    """
    client.lag = (time() * 1000) - client.last_ping_sent

    if client.user:
        if not client.registered:
            cmd_nospoof(client, recv[1].lstrip(':'))

        if client.registered:
            return

        if client.handshake_finished():
            client.register_user()


def init(module):
    Command.add(module, cmd_pong, "PONG", 1, Flag.CMD_USER, Flag.CMD_UNKNOWN, Flag.CMD_SERVER)
    Command.add(module, cmd_ping, "PING", 1, Flag.CMD_USER, Flag.CMD_UNKNOWN, Flag.CMD_SERVER)
