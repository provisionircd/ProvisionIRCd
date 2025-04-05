"""
/netinfo command (server)
"""

import hashlib
from time import time

from handle.core import IRCD, Command, Flag
from handle.logger import logging


def cmd_netinfo(client, recv):
    if not client.local:
        return

    maxglobal = int(recv[1])
    IRCD.maxgusers = max(IRCD.maxgusers, maxglobal)
    end_of_sync = int(recv[2])
    version = recv[3]
    cloakhash = recv[4]
    creation = int(recv[5])
    remotename = recv[8].removeprefix(':')
    current_time = int(time())
    remotehost = client.name

    if remotename != IRCD.me.name and client.name == remotename:
        data = f"*** Network name mismatch from {client.name} ({remotename} != {IRCD.me.name}"
        IRCD.log(IRCD.me, "warn", "link", "NETWORK_NAME_MISMATCH", data, sync=0)

    if version != IRCD.versionnumber.replace('.', '') and not client.is_uline() and client.name == remotename:
        data = (f"*** Remote server {remotehost} is using version {version},"
                f"and we are using version {IRCD.versionnumber.replace('.', '')}, but this should not cause issues.")
        IRCD.log(IRCD.me, "warn", "link", "VERSION_MISMATCH", data, sync=0)

    if creation:
        client.creationtime = creation

    if cloakhash.split(':')[1] != hashlib.md5(IRCD.get_setting("cloak-key").encode("utf-8")).hexdigest():
        data = "*** (warning) Network wide cloak keys are not the same! This will affect channel bans and must be fixed!"
        IRCD.log(IRCD.me, "warn", "link", "CLOAK_KEY_MISMATCH", data, sync=0)

    if not client.uplink.server.synced:
        sync_time = current_time - end_of_sync
        msg = (f"Link {client.uplink.name} -> {client.name} synced [seconds: {sync_time}, "
               f"recv: {client.local.bytes_received}, sent: {client.local.bytes_sent}]")
        IRCD.log(client.uplink, "info", "link", "SERVER_SYNCED", msg, sync=0)


def init(module):
    Command.add(module, cmd_netinfo, "NETINFO", 2, Flag.CMD_SERVER)
