"""
SASL support
"""

from time import time

from handle.core import Numeric, IRCD, Flag, Command, Capability, Hook
from handle.logger import logging
from handle.validate_conf import conf_error


# Drafts:
# https://ircv3.net/specs/extensions/sasl-3.1
# https://ircv3.net/specs/extensions/sasl-3.2
# https://tools.ietf.org/html/rfc4422 (EXTERNAL mechanism, certs)
# https://tools.ietf.org/html/rfc4616 (PLAIN mechanism, most commonly used)
# https://gist.github.com/grawity/8389307


class SaslRequest:
    table = []

    def __init__(self, client, user_id):
        self.client = client
        self.user_id = user_id
        self.token = None
        self.failed_attempts = 0
        self.mech = None
        SaslRequest.table.append(self)

    @staticmethod
    def get_from_id(client_id):
        return next((c for c in SaslRequest.table if c.user_id == client_id), 0)

    def __repr__(self):
        return f"<SaslRequest '{self.user_id}', Client: '{self.client.name}', Token: '{self.token}', Mech: '{self.mech}'>"


class SaslInfo:
    server = None

    # Dictionary to hold request init times to check for timeouts.
    request_init = {}

    # Dictionary to hold failed attempts per client.
    failed_attempts = {}


def cmd_authenticate(client, recv):
    if not client.user:
        return

    if not SaslInfo.server:
        return client.sendnumeric(Numeric.ERR_SASLFAIL)

    if not (saslrequest := SaslRequest.get_from_id(client.id)):
        saslrequest = SaslRequest(client=client, user_id=client.id)
        saslrequest.mech = recv[1]
        data = f":{IRCD.me.name} SASL {SaslInfo.server.name} {client.id} H {client.ip} {client.ip}"
        IRCD.send_to_servers(client, [], data)
        data = f":{IRCD.me.name} SASL {SaslInfo.server.name} {client.id} S {recv[1]}"
        IRCD.send_to_servers(client, [], data)
        return

    if not saslrequest.token and saslrequest.mech:
        saslrequest.token = recv[1]
        data = f":{IRCD.me.name} SASL {SaslInfo.server.name} {client.id} C {recv[1]}"
        IRCD.send_to_servers(client, [], data)


def cmd_sasl(client, recv):
    # logging.debug(f"SASL from client {client.name}: {recv}")
    SaslInfo.server = IRCD.find_server(IRCD.get_setting("sasl-server"))
    if not SaslInfo.server:
        logging.debug(f"SASL request received but SASL server is offline")
        return

    if not (saslrequest := SaslRequest.get_from_id(recv[2])):
        saslrequest = SaslRequest(client=client, user_id=recv[2])

    if recv[1] in [IRCD.me.name, IRCD.me.id]:
        # :00B SASL dev.provisionweb.org <C|D> [...]
        target_client = IRCD.find_user(recv[2])
        if not target_client:
            return
        if recv[3] == "C":
            target_client.send([], f"AUTHENTICATE {recv[4]}")

        elif recv[3] == "D":  # Done?
            SaslRequest.table.remove(saslrequest)
            if recv[4] == "S":  # Success?
                target_client.sendnumeric(Numeric.RPL_SASLSUCCESS)

            elif recv[4] == "F":  # Fail.
                target_client.sendnumeric(Numeric.ERR_SASLFAIL)
                saslrequest.mech = None
                saslrequest.failed_attempts += 1
                if saslrequest.failed_attempts >= 3:
                    target_client.client.exit("Too many SASL authentication failures")
        return

    data = f":{client.name} {' '.join(recv)}"
    sasl_direction = IRCD.find_server(recv[1])
    IRCD.send_to_one_server(sasl_direction, [], data)


def cmd_svslogin(client, recv):
    # :00B SVSLOGIN dev.provisionweb.org 001GUS2CA Sirius
    if auth_client := IRCD.find_user(recv[2]):
        account = recv[3]
        # auth_client.sendnumeric(Numeric.RPL_LOGGEDIN, account)
        # auth_client.sendnumeric(Numeric.RPL_SASLSUCCESS)
        curr_account = auth_client.user.account
        auth_client.user.account = account
        if account != curr_account:
            IRCD.run_hook(Hook.ACCOUNT_LOGIN, auth_client)

    data = f":{client.id} {' '.join(recv)}"
    IRCD.send_to_servers(client, [], data)


def check_sasl_timeout():
    if not (sasl_server := IRCD.find_server(IRCD.get_setting('sasl-server'))):
        SaslInfo.server = None
    elif sasl_server.server.synced and not sasl_server.exitted:
        SaslInfo.server = sasl_server
        if not not Capability.find_cap("sasl"):
            mech = SaslInfo.server.get_md_value("saslmechlist")
            Capability.add("sasl", mech)

    # Checking for SASL timeouts on clients.
    for client_id in list([r for r in SaslInfo.request_init if int(time()) - SaslInfo.request_init[r] > 2]):
        # logging.debug(f"SASL auth timed out for {client.name}")
        if client := IRCD.find_user(client_id):
            IRCD.server_notice(client, "SASL request timed out (server or client misbehaving) -- aborting SASL and continuing connection...")
            client.sendnumeric(Numeric.ERR_SASLABORTED)
        del SaslInfo.request_init[client_id]


def sasl_cleanup(client, reason):
    # Cleanups after client quit.
    if authrequest := SaslRequest.get_from_id(client.id):
        SaslRequest.table.remove(authrequest)


def sasl_server_online(client):
    if client.name == IRCD.get_setting('sasl-server'):
        SaslInfo.server = client
        logging.debug(f"Registered SASL server: {client.name}")
        mech = SaslInfo.server.get_md_value("saslmechlist")
        Capability.add("sasl", mech)


def sasl_server_offline(client):
    if client == SaslInfo.server:
        Capability.remove("sasl")


def post_load(module):
    if not IRCD.get_setting("sasl-server"):
        conf_error("[m_sasl] Missing requirement in conf: settings::sasl-server must be a valid server")
    SaslInfo.server = IRCD.find_server(IRCD.get_setting("sasl-server"))


def init(module):
    # Only add SASL capability if the SASL server is currently online.
    # No use in advertising SASL support without the SASL server.
    if SaslInfo.server:
        mech = SaslInfo.server.get_md_value("saslmechlist")
        Capability.add("sasl", mech)

    Hook.add(Hook.LOOP, check_sasl_timeout)
    Hook.add(Hook.LOCAL_QUIT, sasl_cleanup)
    Hook.add(Hook.REMOTE_QUIT, sasl_cleanup)
    Hook.add(Hook.SERVER_SYNCED, sasl_server_online)
    Hook.add(Hook.SERVER_DISCONNECT, sasl_server_offline)
    Command.add(module, cmd_sasl, "SASL", 2, Flag.CMD_UNKNOWN)
    Command.add(module, cmd_authenticate, "AUTHENTICATE", 1, Flag.CMD_UNKNOWN)
    Command.add(module, cmd_svslogin, "SVSLOGIN", 2, Flag.CMD_SERVER)
