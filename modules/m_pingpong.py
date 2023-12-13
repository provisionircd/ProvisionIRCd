"""
ping/pong handler
"""

from time import time
from handle.core import Flag, Command, IRCD
from handle.logger import logging


def cmd_ping(client, recv):
    if client.server:
        if not (ping_from := IRCD.find_server(recv[1])):
            logging.error(f"Ping from unknown server: {recv[1]}")
            return
        if not (ping_to := IRCD.find_server(recv[2])):
            logging.error(f"Server {ping_from.name} tries to ping unknown server: {recv[2]}")
            return
        data = f":{ping_to.id} PONG {ping_to.name} {ping_from.name}"
        client.send([], data)
        return
    response = recv[1].removeprefix(':')
    client.send([], f":{IRCD.me.name} PONG {IRCD.me.name} :{response}")


def cmd_nospoof(client, reply):
    if reply == client.local.nospoof:
        client.local.nospoof = 0
    else:
        IRCD.server_notice(client, "ERROR: Invalid PING response. Your client must respond back with PONG :<cookie>")


def cmd_pong(client, recv):
    """
    Reply to a PING command.
    """

    client.lag = (time() * 1000) - client.last_ping_sent

    if client.user:
        if not client.registered:
            reply = recv[1]
            if reply.startswith(':'):
                reply = reply[1:]
            cmd_nospoof(client, reply)

        if client.registered:
            return

        if client.handshake_finished():
            client.register_user()


def init(module):
    Command.add(module, cmd_pong, "PONG", 1, Flag.CMD_USER, Flag.CMD_UNKNOWN, Flag.CMD_SERVER)
    Command.add(module, cmd_ping, "PING", 0, Flag.CMD_USER, Flag.CMD_UNKNOWN, Flag.CMD_SERVER)
