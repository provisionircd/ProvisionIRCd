"""
/starttls command
"""

import ircd

@ircd.Modules.command
class Starttls(ircd.Command):
    def __init__(self):
        self.command = 'starttls'

    def execute(self, client, recv):
        if client.registered or not client.socket:
            return
        try:
            if not self.ssl:
                client.sendraw(670, ':STARTTLS successful, proceed with TLS handshake')
                port = client.socket.getsockname()[1]
                client.socket = self.ircd.sslctx[port].wrap_socket(client.socket, server_side=True)
                client.ssl = True
            else:
                client.sendraw(691, ':STARTTLS failed. Already using TLS.')
        except Exception as ex:
            client.sendraw(691, ':STARTTLS failure: {}'.format(str(ex)))
            client.quit('STARTTLS failed. Make sure your client supports STARTTLS: {}'.format(str(ex)), error=True)
