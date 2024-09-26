"""
/netinfo command (server)
"""

import hashlib
import time

from handle.core import Command, IRCD, Flag


def cmd_netinfo(client, recv):
    maxglobal = int(recv[1])
    if maxglobal > IRCD.maxgusers:
        IRCD.maxgusers = maxglobal

    remotetime = int(recv[2])
    version = recv[3]
    cloakhash = recv[4]
    creation = int(recv[5])
    remotename = recv[8][1:]
    currenttime = int(time.time())
    remotehost = client.name

    if abs(remotetime - currenttime) > 60:
        if abs(remotetime - currenttime) > 300 and client.local:
            err = "ERROR :Link denied due to incorrect clocks. Please make sure both clocks are synced!"
            client.direct_send(err)
            client.exit(err)
            return

        diff = abs(remotetime - currenttime)
        if remotetime != currenttime:
            status = "ahead" if remotetime > currenttime else "behind"
            IRCD.send_snomask(IRCD.me, 's',
                              f"*** (warning) Remote server {remotehost}'s clock is ~{diff}s {status} on ours, this can cause issues and should be fixed!")

    if remotename != IRCD.me.name and client.name == remotename:
        IRCD.send_snomask(IRCD.me, 's', f"*** Network name mismatch from {client.name} ({remotename} != {IRCD.me.name})")

    if version != IRCD.versionnumber.replace('.', '') and not client.ulined and client.name == remotename:
        IRCD.send_snomask(IRCD.me, 's',
                          f"*** Remote server {remotehost} is using version {version}, and we are using version {IRCD.versionnumber.replace('.', '')}, but this should not cause issues.")

    if creation:
        client.creationtime = creation

    if not client.server.synced:
        secure = 1 if client.local and client.local.tls else 0 if client.local else -1
        prefix = "Secure l" if secure == 1 else "Unsecure l" if secure == 0 else 'L'
        msg = f"{prefix}ink {client.uplink.name} -> {client.name} successfully established"
        IRCD.log(client.uplink, "info", "link", "LINK_ESTABLISHED", msg, sync=0)

    if cloakhash.split(':')[1] != hashlib.md5(IRCD.get_setting("cloak-key").encode("utf-8")).hexdigest():
        IRCD.send_snomask(IRCD.me, 's', "*** (warning) Network wide cloak keys are not the same! This will affect channel bans and must be fixed!")

    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def init(module):
    Command.add(module, cmd_netinfo, "NETINFO", 2, Flag.CMD_SERVER)
