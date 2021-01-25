"""
/starttls command
"""

import ssl

import ircd


@ircd.Modules.command
class Starttls(ircd.Command):
    def __init__(self):
        self.command = 'starttls'
        self.cap = 'tls'

    def execute(self, client, recv):
        if client.registered or not client.socket:
            return
        try:
            if not client.ssl:
                # client.sendraw(670, ':STARTTLS successful, proceed with TLS handshake')
                client.socket.send(bytes(':{} 670 {} :STARTTLS successful, proceed with TLS handshake\r\n'.format(self.ircd.hostname, client.nickname), 'utf-8'))
                sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
                sslctx.load_cert_chain(certfile=self.ircd.default_cert, keyfile=self.ircd.default_key)
                sslctx.load_default_certs(purpose=ssl.Purpose.CLIENT_AUTH)
                sslctx.load_verify_locations(cafile=self.ircd.default_ca_file)
                sslctx.verify_mode = ssl.CERT_NONE
                client.socket = sslctx.wrap_socket(client.socket, server_side=True)
                client.ssl = True
            else:
                client.sendraw(691, ':STARTTLS failed. Already using TLS.')
        except Exception as ex:
            client.sendraw(691, ':STARTTLS failure: {}'.format(str(ex)))
            client.quit('STARTTLS failed. Make sure your client supports STARTTLS: {}'.format(str(ex)), error=True)
