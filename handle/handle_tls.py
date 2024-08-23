# https://www.pyopenssl.org/en/latest/api/ssl.html

import os

from OpenSSL import SSL, crypto
from handle.logger import logging
from handle.core import IRCD


def ssl_verify_callback(*args):
    return 1


def create_ctx(cert, key, name=None):
    try:
        if not os.path.exists("tls"):
            os.mkdir("tls")
        missing = 0
        if not os.path.isfile(cert):
            logging.error(f"Unable to find certificate file: {cert}")
            missing = 1
        if not os.path.isfile(key):
            logging.error(f"Unable to find certificate file: {key}")
            missing = 1

        if missing:
            answer = input("You have missing TLS files. Would you like to generate now? [Y/n] ")
            if not answer.strip() or answer.strip().lower() == "y":
                generate_cert(key, cert, name)
            else:
                exit()

        tlsctx = SSL.Context(method=SSL.TLS_METHOD)
        tlsctx.use_privatekey_file(key)
        tlsctx.use_certificate_file(cert)
        tlsctx.use_certificate_chain_file(cert)
        tlsctx.set_verify(SSL.VERIFY_PEER, callback=ssl_verify_callback)

        if not IRCD.default_tlsctx:
            IRCD.default_tlsctx = tlsctx
        return tlsctx
    except Exception as ex:
        logging.exception(ex)
        exit()


def wrap_socket(listen_obj):
    return SSL.Connection(listen_obj.tlsctx, listen_obj.sock)


def generate_cert(key_out, cert_out, name):
    if not name:
        logging.error(f"Missing name in generate_cert()")
        exit()
        return
    # create a key pair
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)

    # create a self-signed cert
    cert = crypto.X509()
    # https://cryptography.io/en/latest/x509/tutorial/#creating-a-self-signed-certificate

    default_C = "NL"
    default_ST = "Some-Province"
    default_L = "Amsterdam"
    default_OU = "Example Ltd"
    default_CN = name
    C = input(f"Country code [{default_C}]: ")
    if not C:
        C = default_C
    ST = input(f"Province or state [{default_ST}]: ")
    if not ST:
        ST = default_ST
    L = input(f"Locality name (eg, city) [{default_L.strip()}]: ")
    if not L:
        L = default_L
    OU = input(f"Organization [{default_OU}]: ")
    if not OU:
        OU = default_OU
    CN = input(f"Common Name [{default_CN.strip()}]: ")
    if not CN:
        CN = default_CN
    print("Generating key pair, please wait...")
    cert.get_subject().C = C  # Country
    cert.get_subject().ST = ST  # State or province
    cert.get_subject().L = L  # Locality name
    cert.get_subject().OU = OU  # Organisation name
    cert.get_subject().CN = CN  # Common name
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')

    dirname = os.path.dirname(cert_out)
    if not os.path.exists(dirname):
        os.mkdir(dirname)

    dirname = os.path.dirname(key_out)
    if not os.path.exists(dirname):
        os.mkdir(dirname)

    with open(cert_out, "wb+") as cert_f:
        cert_f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    with open(key_out, "wb+") as key_f:
        key_f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

    print("Ok.")
