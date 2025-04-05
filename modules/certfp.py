"""
Client certificate fingerprint support
"""

from handle.core import IRCD, Numeric, Hook


def certfp_connect(client):
    if fingerprint := client.get_md_value("certfp"):
        IRCD.server_notice(client, f"Your TLS fingerprint is: {fingerprint}")


def extract_client_cn(cert):
    subject = cert.get_subject()
    for component in subject.get_components():
        if component[0] == b"CN":
            return component[1].decode("utf-8")
    return None


def extract_client_san(cert):
    ext_count = cert.get_extension_count()
    for i in range(ext_count):
        ext = cert.get_extension(i)
        if ext.get_short_name() == b"subjectAltName":
            return str(ext)
    return None


def get_certfp(client):
    if not client.local.tls or client.get_md_value("certfp"):
        return

    if not (cert := client.local.socket.get_peer_certificate()):
        return

    if cn := extract_client_cn(cert):
        client.add_md(name="cert_cn", value=cn, sync=0)

    if san := extract_client_san(cert):
        client.add_md(name="cert_san", value=san, sync=0)

    fingerprint = cert.digest("SHA256").decode().lower().replace(':', '')
    client.add_md(name="certfp", value=fingerprint)


def certfp_whois(client, target, lines):
    if fingerprint := target.get_md_value("certfp"):
        line = (Numeric.RPL_WHOISCERTFP, target.name, fingerprint)
        lines.append(line)


def init(module):
    """ Grab certificate first (if any) so that we can work with it. """
    Hook.add(Hook.NEW_CONNECTION, get_certfp, priority=9999)
    Hook.add(Hook.SERVER_LINK_OUT_CONNECTED, get_certfp, priority=9999)
    # Also call get_certfp() on LOCAL_CONNECT for md.sync()
    Hook.add(Hook.LOCAL_CONNECT, get_certfp, priority=9999)
    Hook.add(Hook.LOCAL_CONNECT, certfp_connect)
    Hook.add(Hook.WHOIS, certfp_whois)
