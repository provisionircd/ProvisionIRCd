#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/starttls command
"""

import ircd
import ssl

@ircd.Modules.support('STARTTLS')
@ircd.Modules.commands('starttls')
def starttls(self, localServer, recv):
    try:
        if self.registered:
            return
        if self.socket:
            if not self.ssl:
                self.socket.send(bytes(':{} 670 {} :STARTTLS successful, proceed with TLS handshake\r\n'.format(localServer.hostname, self.nickname), 'utf-8'))
                server_cert = '../ssl/server.cert.pem'
                server_key = '../ssl/server.key.pem'
                ca_certs = '../ssl/curl-ca-bundle.crt'
                sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
                sslctx.load_cert_chain(certfile=server_cert, keyfile=server_key)
                sslctx.load_default_certs(purpose=ssl.Purpose.CLIENT_AUTH)
                sslctx.load_verify_locations(cafile=ca_certs)
                sslctx.verify_mode = ssl.CERT_NONE
                self.socket = sslctx.wrap_socket(self.socket, server_side=True)
                self.ssl = True
            else:
                self.sendraw(691, ':STARTTLS failed. Already using TLS.')
    except Exception as ex:
        self.socket.send(bytes(':{} 691 {} :STARTTLS failure: {}\r\n'.format(localServer.hostname, self.nickname, str(ex)), 'utf-8'))
        self.quit('STARTTLS failed. Make sure your client supports STARTTLS: {}'.format(str(ex)), error=True)
