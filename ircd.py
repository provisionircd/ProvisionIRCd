#!/usr/bin python3

import argparse, sys, os

from OpenSSL.crypto import load_certificate, FILETYPE_PEM, Error

from classes.configuration import ConfigBuild
from handle.logger import logging
from handle.core import Server, IRCD
from handle.sockets import handle_connections
from handle.log import log

if __name__ == "__main__":
    if sys.platform.startswith("linux") and os.geteuid() == 0:
        print("Do not run as root.")
        exit()

    parser = argparse.ArgumentParser(description="ProvisionIRCd")
    parser.add_argument("-c", "--conf", help="Relative path to main configuration file", default="ircd.conf")
    parser.add_argument("--debug", help="Show debug output in console", action="store_true")
    parser.add_argument("--fork", help="Fork to the background", action="store_true")
    parser.add_argument("--certfp", help="Prints the server certificate fingerprint", action="store_true")
    parser.add_argument("--certcn", help="Prints the server certificate CN", action="store_true")

    try:
        import bcrypt

        parser.add_argument("--mkpasswd", help="Generate bcrypt password")
        mkp = 1
    except ImportError:
        mkp = 0

    args = parser.parse_args()

    if mkp and args.mkpasswd:
        hashed = bcrypt.hashpw(args.mkpasswd.encode(), bcrypt.gensalt()).decode()
        print(f"Your salted password: {hashed}")
        exit()

    if args.certfp:
        for file in [file for file in os.listdir("tls") if file.endswith(".pem")]:
            with open("tls/" + file, "rb") as cert:
                try:
                    cert = cert.read()
                    cert = load_certificate(FILETYPE_PEM, cert)
                    fingerprint = cert.digest("sha256").decode().replace(':', '').lower()
                    print(f"[{file}] Fingerprint: {fingerprint}")
                except Error:
                    pass
        exit()

    if args.certcn:
        for file in [file for file in os.listdir("tls") if file.endswith(".pem")]:
            with open("tls/" + file, "rb") as cert:
                try:
                    cert_data = cert.read()
                    cert = load_certificate(FILETYPE_PEM, cert_data)

                    # Extract the CN (Common Name) from the subject
                    subject = cert.get_subject()
                    cn = subject.commonName
                    cn = cn.replace(' ', '_')
                    print(f"[{file}] CN: {cn}")
                except Error:
                    pass
        exit()

    if sys.version_info < (3, 10, 0):
        print("Python version 3.10 or higher is required.")
        sys.exit()

    try:
        IRCD.me = Server()
        if ConfigBuild(conffile=args.conf, debug=args.debug).is_ok():
            IRCD.boot(fork=args.fork)
            handle_connections()
    except Exception as ex:
        logging.exception(ex)
