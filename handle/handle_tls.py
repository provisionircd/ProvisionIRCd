# https://www.pyopenssl.org/en/latest/api/ssl.html

import os

from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from OpenSSL import SSL, crypto
from handle.logger import logging
from handle.core import IRCD


def ssl_verify_callback(*args):
    return True


def create_ctx(cert, key, name=None):
    try:

        os.makedirs("tls", mode=0o755, exist_ok=True)
        missing = 0

        if not os.path.isfile(cert):
            logging.error(f"Unable to find certificate file: {cert}")
            missing = 1
        if not os.path.isfile(key):
            logging.error(f"Unable to find key file: {key}")
            missing = 1

        if missing:
            answer = input("You have missing TLS files. Would you like to generate now? [Y/n] ")
            if not answer.strip() or answer.strip().lower() == 'y':
                generate_cert(key, cert, name)
            else:
                exit()

        tlsctx = SSL.Context(method=SSL.TLS_METHOD)
        tlsctx.set_options(SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3 | SSL.OP_NO_TLSv1 | SSL.OP_NO_TLSv1_1)
        tlsctx.use_privatekey_file(key)
        tlsctx.use_certificate_file(cert)
        tlsctx.use_certificate_chain_file(cert)
        tlsctx.set_verify(SSL.VERIFY_PEER, callback=ssl_verify_callback)

        IRCD.default_tls["ctx"] = tlsctx
        IRCD.default_tls["keyfile"] = key
        IRCD.default_tls["certfile"] = cert
        return tlsctx

    except (SSL.Error, crypto.Error) as ex:
        logging.error(f"SSL/TLS configuration error: {ex}")
        raise
    except FileNotFoundError as ex:
        logging.error(f"Certificate or key file not found: {ex}")
        raise
    except Exception as ex:
        logging.error(f"Unexpected error in TLS setup: {ex}")
        raise


def generate_cert(key_out, cert_out, name):
    if not name:
        logging.error(f"Missing name in generate_cert()")
        exit()

    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)

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

    basic_constraints = x509.Extension(
        ExtensionOID.BASIC_CONSTRAINTS,
        critical=True,
        value=x509.BasicConstraints(ca=False, path_length=None)
    )

    key_usage = x509.Extension(
        ExtensionOID.KEY_USAGE,
        critical=True,
        value=x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=True, data_encipherment=False,
                            key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False)
    )

    extended_key_usage = x509.Extension(
        ExtensionOID.EXTENDED_KEY_USAGE,
        critical=False,
        value=x509.ExtendedKeyUsage([x509.ObjectIdentifier("1.3.6.1.5.5.7.3.1")])
    )

    cert._extensions = [basic_constraints, key_usage, extended_key_usage]

    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, "sha256")

    dirname = os.path.dirname(cert_out)
    os.makedirs(dirname, mode=0o755, exist_ok=True)

    dirname = os.path.dirname(key_out)
    os.makedirs(dirname, mode=0o755, exist_ok=True)

    with open(cert_out, "wb+") as cert_f:
        cert_f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    with open(key_out, "wb+") as key_f:
        key_f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

    if os.name == "posix":
        os.chmod(key_out, 0o600)

    print("Ok.")
