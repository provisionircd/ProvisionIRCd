#!/usr/bin python3

import argparse
import sys
import os
import time

import select
from OpenSSL.crypto import load_certificate, FILETYPE_PEM, Error

from classes.configuration import ConfigBuild
from handle.logger import logging
from handle.core import Server, IRCD
from handle.sockets import handle_connections
from handle.log import log

if sys.version_info < (3, 10, 0):
    print("Python version 3.10 or higher is required.")
    sys.exit()

if __name__ == "__main__":
    if sys.platform.startswith("linux"):
        if os.geteuid() == 0:
            print("Do not run as root.")
            exit()

    parser = argparse.ArgumentParser(description="ProvisionIRCd")
    parser.add_argument("-c", "--conf", help="Relative path to main configuration file")
    parser.add_argument("--debug", help="Show debug output in console", action="store_true")
    parser.add_argument("--fork", help="Fork to the background", action="store_true")
    parser.add_argument("--certfp", help="Prints the server certificate fingerprint", action="store_true")
    try:
        mkp = 1
        import bcrypt

        parser.add_argument("--mkpasswd", help="Generate bcrypt password.")
    except ImportError:
        mkp = 0
    args = parser.parse_args()
    if not mkp:
        args.mkpasswd = None
    if args.mkpasswd:
        hashed = bcrypt.hashpw(args.mkpasswd.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")
        print(f"Your salted password: {hashed}")
        exit()
    if args.certfp:
        for file in [file for file in os.listdir("tls") if file.endswith(".pem")]:
            with open("tls/" + file, "rb") as cert:
                try:
                    cert = cert.read()
                    cert = load_certificate(FILETYPE_PEM, cert)
                    fingerprint = cert.digest("sha256").decode().replace(':', '').lower()
                    print(f"[{file}]: {fingerprint}")
                except Error:
                    pass
        exit()

    if not args.conf:
        conffile = "ircd.conf"
    else:
        conffile = args.conf
    if sys.version_info < (3, 10, 0):
        print("Python version 3.10 or higher is required.")
        sys.exit()
    try:
        IRCD.me = Server()
        if ConfigBuild(conffile=conffile, debug=args.debug).is_ok():
            IRCD.boot(fork=args.fork)
            handle_connections()
    except Exception as ex:
        logging.exception(ex)
