"""
Minimal websockets support.
"""

import ipaddress
import threading
from time import time
import ssl
from websockets.sync.server import serve
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK
from handle.sockets import post_sockread
from handle.core import IRCD, Hook, Numeric
from handle.client import make_client, make_user
from handle.logger import logging
from handle.validate_conf import conf_error

logging.getLogger("websockets").setLevel(logging.WARNING)


class WebSockets:
    host: str = ''
    port: int = 0
    options = []


def websockets_ping():
    pingfreq = 10
    current_time = time()

    for client in list(IRCD.websocketbridge.clients):
        if (current_time - client.local.last_msg_received) >= 20:
            IRCD.websocketbridge.exit_client(client)
            continue

        time_since_last_ping = (current_time * 1000 - client.last_ping_sent) / 1000
        if (current_time - client.local.last_msg_received) >= pingfreq and time_since_last_ping > pingfreq / 3:
            data = f"PING :{IRCD.me.name}"
            client.send([], data)
            client.last_ping_sent = current_time * 1000


def create_ssl_context(certfile, keyfile):
    if not certfile or not keyfile:
        return
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    return context


class WebSocketIRCBridge:
    clients = []

    def __init__(self):
        self.server = None
        self.host = WebSockets.host
        self.port = WebSockets.port
        self.tls = None if "tls" not in WebSockets.options else create_ssl_context(IRCD.default_tls["certfile"], IRCD.default_tls["keyfile"])
        self.clients = set()

    def start_server(self):
        server_thread = threading.Thread(target=self.run_server, daemon=True)
        server_thread.start()

    def run_server(self):
        try:
            self.server = serve(self.handler, self.host, self.port, ssl_context=self.tls, logger=None)
        except OSError as ex:
            if ex.errno in [13, 10013]:
                return logging.error(f"[WebSockets] Could not bind to port '{self.port}': Permission denied.")
            if ex.errno in [98, 48, 10048]:
                return logging.error(f"[WebSockets] Port '{self.port}' is already in use on this machine")
        except Exception as ex:
            logging.exception(ex)
        logging.debug(f"WebSocket server running at {'wss' if self.tls else 'ws'}://{self.host}:{self.port}")
        self.server.serve_forever()

    def handler(self, websocket):
        client = make_client(direction=None, uplink=IRCD.me)
        client.websocket = websocket
        client.ip, client.port = websocket.remote_address
        client.local.handshake = 1
        client = make_user(client)
        if IRCD.websocketbridge.tls:
            client.local.tls = IRCD.default_tls["ctx"]

        IRCD.websocketbridge.clients.add(client)
        # logging.debug(f"Client connected: IP={client.ip}, port={client.port}")

        try:
            for message in websocket:
                self.process_message(client, message)
        except ConnectionClosed:
            self.exit_client(client)

    def process_message(self, client, message):
        post_sockread(client, message + "\r\n")

    def send_to_client(self, client, message):
        try:
            client.websocket.send(message)
        except (ConnectionClosed, ConnectionClosedOK):
            self.exit_client(client)

    def send_to_all_clients(self, message):
        for client in list(IRCD.websocketbridge.clients):
            try:
                self.send_to_client(client, message)
            except (ConnectionClosed, ConnectionClosedOK):
                self.exit_client(client)

    def exit_client(self, client, reason="Connection closed"):
        if client in IRCD.websocketbridge.clients:
            IRCD.websocketbridge.clients.remove(client)
            client.exit(reason)
        client.websocket.close()


def start_websockets():
    if not IRCD.websocketbridge:
        IRCD.websocketbridge = WebSocketIRCBridge()
        IRCD.websocketbridge.start_server()


def websockets_whois(client, whois_client, lines):
    if whois_client.websocket:
        line = (Numeric.RPL_WHOISSPECIAL, whois_client.name, "is connected via WebSockets")
        lines.append(line)


def post_load(module):
    if not (websockets_settings := IRCD.configuration.get_items("settings:websockets")):
        return conf_error("WebSockets module is loaded but settings:websockets { } block is missing in configuration file")

    host = port = None
    for entry in websockets_settings:
        entry_name, entry_value = entry.path[1:3]
        if entry_name == "host":
            host = entry_value
        elif entry_name == "port":
            port = entry_value
        elif entry_name == "options":
            WebSockets.options.append(entry_value)

    if not host:
        return conf_error(f"settings:websockets:host missing")

    if host != '*':
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return conf_error(f"settings:websockets:host is invalid: must be a valid IP address")
    else:
        host = "0.0.0.0"
    if not port or not port.isdigit():
        return conf_error(f"settings:websockets:port missing or invalid: must be a digit between 1024-65535")

    if not 1024 <= int(port) <= 65535:
        return conf_error(f"settings:websockets:port is invalid: must be in range 1024-65535")

    WebSockets.host, WebSockets.port = host, int(port)
    Hook.add(Hook.BOOT, start_websockets)
    Hook.add(Hook.LOOP, websockets_ping)
    Hook.add(Hook.WHOIS, websockets_whois)
