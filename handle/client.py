import random
import string
import sys
from time import time

import select

from handle.functions import logging
from handle.core import IRCD, Client, Server, User, LocalClient

try:
    READ_ONLY = (
            select.POLLIN |
            select.POLLPRI |
            select.POLLHUP |
            select.POLLERR
    )
    READ_WRITE = READ_ONLY | select.POLLOUT
except AttributeError:
    if sys.platform.startswith("win32"):
        logging.warning("Windows does not support select.poll(), using select.select() instead.")
        IRCD.use_poll = 0


def make_client(direction, uplink) -> Client:
    """
    direction           The locally connected server who introduced this client. For local clients this will be None.
    uplink              The server to which this client is uplinked. This can be this server, if it is a local client.
    """
    if direction and not direction.local:
        logging.error(f"Could not make_client(), 'direction' should be None (for locally accepted clients), or a local client when creating a new remote client!")
        logging.error(f"Direction was: {direction.name}")
        exit()
        return
    client = Client()
    client.direction = direction if direction else uplink
    client.uplink = uplink
    client.creationtime = int(time())
    client.idle_since = int(time())
    IRCD.global_client_count += 1
    if not direction:
        # Local client.
        IRCD.local_client_count += 1
        client.local = LocalClient()
        client.local.creationtime = int(time())
    Client.table.append(client)
    return client


def make_server(client: Client):
    client.server = Server()
    if client.uplink == IRCD.me:
        client.direction = client
    return client


def make_user(client: Client):
    client.user = User()
    if client.local:
        client.id = IRCD.get_first_available_uid(client)
        client.assign_host()
        client.local.nospoof = ''.join(random.choice(string.digits + string.ascii_uppercase) for _ in range(8))
        client.send([], f"PING :{client.local.nospoof}")

    return client


def find_client_from_socket(socket):
    for client in IRCD.local_clients():
        if client.local.socket == socket:
            return client


def find_listen_obj_from_socket(socket):
    for listen_obj in IRCD.configuration.listen:
        if listen_obj.sock == socket:
            return listen_obj
