"""
/version command
"""

import OpenSSL

from handle.core import IRCD, Command, Isupport, Numeric


def cmd_version(client, recv):
    client.sendnumeric(Numeric.RPL_VERSION, IRCD.version, IRCD.me.name, IRCD.hostinfo)
    if client.local.tls:
        IRCD.server_notice(client, f":{OpenSSL.SSL.SSLeay_version(OpenSSL.SSL.SSLEAY_VERSION).decode()}")

    Isupport.send_to_client(client)


def init(module):
    Command.add(module, cmd_version, "VERSION")
