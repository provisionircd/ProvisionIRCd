from handle.core import Numeric, IRCD, Hook
from handle.logger import logging


def certfp_connect(client):
    if fingerprint := client.get_md_value("certfp"):
        IRCD.server_notice(client, f"Your TLS fingerprint is: {fingerprint}")


def certfp_new_connection(client):
    if not client.local.tls:
        return
    fingerprint = client.local.socket.get_peer_certificate()
    if not fingerprint:
        # Client did not send a cert.
        return
    fingerprint = fingerprint.digest("SHA256").decode().lower().replace(":", "")
    client.add_md(name="certfp", value=fingerprint)


def certfp_whois(client, target, lines):
    if fingerprint := target.get_md_value("certfp"):
        line = (Numeric.RPL_WHOISCERTFP, target.name, fingerprint)
        lines.append(line)


def init(module):
    """ Grab certificate first (if any) so that we can work with it. """
    Hook.add(Hook.NEW_CONNECTION, certfp_new_connection, priority=9999)
    Hook.add(Hook.LOCAL_CONNECT, certfp_connect)
    Hook.add(Hook.WHOIS, certfp_whois)
