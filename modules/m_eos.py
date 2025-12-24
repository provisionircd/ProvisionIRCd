"""
/eos command (server)
"""

from handle.core import IRCD, Command, Flag, Hook
from modules.ircv3.batch import Batch
from handle.logger import logging


@logging.client_context
def cmd_eos(client, recv):
    # TODO: Check:
    #  if IRCD.current_link_sync in [client, client.uplink, client.direction]:
    if IRCD.current_link_sync == client:
        IRCD.current_link_sync = None

    if client.server.synced:
        return

    client.server.synced = 1
    client.add_flag(Flag.CLIENT_REGISTERED)

    IRCD.send_to_servers(client, mtags=[], data=f":{client.id} EOS")
    logging.info(f"[cmd_eos()] EOS received for {client.name}. Marked as synced. Uplink: {client.uplink.name})")

    # TODO: Test: swapped send_after_eos and do_delayed_process()
    """ Send held back data for this client """
    if client in IRCD.send_after_eos:
        logging.debug(f"Now sending previously held back server data to {client.name}")
        for mtags, data in IRCD.send_after_eos[client]:
            IRCD.send_to_one_server(client, mtags, data)
        del IRCD.send_after_eos[client]

    """ We can now process other servers' recv buffer """
    IRCD.do_delayed_process()

    for batch in Batch.pool:
        started_by = client if client.local else client.uplink
        if batch.started_by in [started_by, started_by.direction] and batch.batch_type == "netjoin":
            batch.end()

    IRCD.run_hook(Hook.SERVER_SYNCED, client)


def init(module):
    Command.add(module, cmd_eos, "EOS", 0, Flag.CMD_SERVER)
