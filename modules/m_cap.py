"""
/cap command
"""

from handle.core import Numeric, Flag, IRCD, Command, Capability, Hook
from handle.logger import logging


class Cap_handshake:
    in_progress = []


def cmd_cap(client, recv):
    if len(recv) < 2:
        return

    if recv[1].lower() == "ls":
        # Don't reg until CAP END
        if client not in Cap_handshake.in_progress:
            Cap_handshake.in_progress.append(client)
        caps = []
        for c in Capability.table:
            caps.append(c.string)
        client.send([], f":{IRCD.me.name} CAP {client.name} LS :{' '.join(caps)}")

    elif recv[1].lower() == "list":
        if client.local.caps:
            data = f":{IRCD.me.name} CAP {client.name} LIST :{' '.join(client.local.caps)}"
            client.send([], data)

    elif recv[1].lower() == "req":
        # Don't reg until CAP END
        if client not in Cap_handshake.in_progress:
            Cap_handshake.in_progress.append(client)
        if len(recv) < 3:
            return

        caps = ' '.join(recv[2:]).lower().removeprefix(':')
        ack_caps = []
        for cap in caps.split():
            if cap.startswith("-"):
                cap = cap[1:]
                if cap in client.local.caps:
                    client.local.caps.remove(cap)
                    ack_caps.append('-' + cap)
                continue

            if (find_cap := Capability.find_cap(cap)) and find_cap.name not in client.local.caps:
                client.local.caps.append(find_cap.name)
                ack_caps.append(cap)

        if ack_caps:
            data = f":{IRCD.me.name} CAP {client.name} ACK :{' '.join(ack_caps)}"
            client.send([], data)

    elif recv[1].lower() == "end":
        if client.registered:
            return
        if client in Cap_handshake.in_progress:
            Cap_handshake.in_progress.remove(client)
        if client.user:
            if client.handshake_finished():
                client.register_user()
    else:
        client.sendnumeric(Numeric.ERR_INVALIDCAPCMD, recv[1])


def cap_handshake_finished(client):
    return client not in Cap_handshake.in_progress


def cap_cleanup(client, reason):
    if client in Cap_handshake.in_progress:
        Cap_handshake.in_progress.remove(client)


def init(module):
    Command.add(module, cmd_cap, "CAP", 1, Flag.CMD_USER, Flag.CMD_SERVER, Flag.CMD_UNKNOWN)
    Capability.add("cap-notify")
    Hook.add(Hook.IS_HANDSHAKE_FINISHED, cap_handshake_finished)
    Hook.add(Hook.LOCAL_QUIT, cap_cleanup)
