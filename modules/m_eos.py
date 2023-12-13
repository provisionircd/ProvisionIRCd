"""
/eos command (server)
"""

from handle.core import Command, Flag, IRCD, Hook, Batch
from handle.handleLink import broadcast_new_server_to_network, broadcast_network_to_new_server, sync_data
from handle.logger import logging


def cmd_eos(client, recv):
    if client.server.synced:
        return

    IRCD.send_to_servers(client, mtags=[], data=f":{client.id} EOS")
    logging.debug(f"EOS received by: {client.name} (uplink: {client.uplink.name})")

    client.server.synced = 1
    client.add_flag(Flag.CLIENT_REGISTERED)

    # for server_client in [c for c in IRCD.global_servers() if c.direction == client and c != client]:
    #     server_client.server.synced = 1
    #     server_client.add_flag(Flag.CLIENT_REGISTERED)
    #     IRCD.run_hook(Hook.SERVER_SYNCED, server_client)

    IRCD.run_hook(Hook.SERVER_SYNCED, client)
    IRCD.do_delayed_process()

    if client in IRCD.send_after_eos:
        logging.warning(f"Now sending previously held back server data to {client.name}")
        for mtags, data in IRCD.send_after_eos[client]:
            logging.warning(f"Delayed data: {data.rstrip()}")
            IRCD.send_to_one_server(client, mtags, data)

    for batch in Batch.pool:
        started_by = client if client.local else client.uplink
        if batch.started_by in [started_by, started_by.direction] and batch.batch_type == "netjoin":
            batch.end()


def init(module):
    Command.add(module, cmd_eos, "EOS", 0, Flag.CMD_SERVER, Flag.CMD_UNKNOWN)
