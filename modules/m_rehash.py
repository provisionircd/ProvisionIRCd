"""
/rehash command
"""

from classes.configuration import ConfigBuild
from handle.core import Command, IRCD, Numeric, Flag
import gc

gc.enable()


def cmd_rehash(client, recv):
    """
    Reloads the configuration files.
    """
    if client.user and not client.has_permission("server:rehash"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
    if IRCD.rehashing:
        return

    IRCD.rehashing = 1
    IRCD.current_link_sync = None
    if client.is_local_user:
        client.local.flood_penalty += 500_000
    if client.user:
        msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) is rehashing the server configuration file..."
    else:
        msg = f"*** Rehashing configuration file from the command line..."
    IRCD.log(client, "info", "config", "CONFIG_REHASH", msg)

    reloadmods = 0
    if len(recv) > 1:
        for flag in recv[1:]:
            if flag.lower() == "--reload-mods":
                client.local.flood_penalty += 1_000_000
                reloadmods = 1
                msg = f"*** Also reloading all modules."
                IRCD.log(client, "info", "config", "CONFIG_REHASH", msg)

    client.sendnumeric(Numeric.RPL_REHASHING, IRCD.conf_path)
    if ConfigBuild(conffile=IRCD.conf_file).is_ok(rehash=1, rehash_client=client, reloadmods=reloadmods):
        msg = "*** Configuration reloaded without any problems."
    else:
        msg = "*** Configuration failed to reload."

    IRCD.log(client, "info", "config", "CONFIG_REHASH", msg)

    gc.collect()
    IRCD.rehashing = 0


def init(module):
    Command.add(module, cmd_rehash, "REHASH", 0, Flag.CMD_OPER)
