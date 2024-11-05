"""
/starttls command
"""

from handle.core import IRCD, Command, Numeric, Capability, Flag
from handle.sockets import wrap_socket


def cmd_starttls(client, recv):
    if not client.local or client.registered:
        return
    try:
        if not client.local.tls:
            client.local.handshake = 0
            client.sendnumeric(Numeric.RPL_STARTTLS, "STARTTLS successful, proceed with TLS handshake")
            IRCD.run_parallel_function(wrap_socket, args=(client,), kwargs={"starttls": 1})
        else:
            client.sendnumeric(Numeric.ERR_STARTTLS, "Already using TLS.")
    except Exception as ex:
        client.sendnumeric(Numeric.ERR_STARTTLS, str(ex) or "unknown error")
        client.exit(f"STARTTLS failed. Make sure your client supports STARTTLS: {str(ex) or 'unknown error'}")


def init(module):
    Command.add(module, cmd_starttls, "STARTTLS", 0, Flag.CMD_UNKNOWN)
    Capability.add("tls")
