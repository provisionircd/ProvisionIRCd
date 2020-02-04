"""
/connect command
"""

import ircd

from handle.handleLink import Link
from handle.functions import logging

def connectTo(self, ircd, name, autoLink=False):
    try:
        host, port = ircd.conf['link'][name]['outgoing']['host'], ircd.conf['link'][name]['outgoing']['port']
        # If the host is local, and you are listening for servers on the port, do not connect to yourself.
        if host in ['127.0.0.1', '0.0.0.0', 'localhost'] and (port in ircd.conf['listen'] and ircd.conf['listen'][str(port)]['options'] == 'servers'):
            return
        pswd = ircd.conf['link'][name]['pass']
        is_ssl = False
        if 'options' in ircd.conf['link'][name] and ('tls' in ircd.conf['link'][name]['options'] or 'ssl' in ircd.conf['link'][name]['options']):
            is_ssl = True
        l = Link(self, ircd, name, host, port, pswd, is_ssl, autoLink)
        l.start()

    except Exception as ex:
        logging.exception(ex)



@ircd.Modules.command
class Connect(ircd.Command):
    """
    Used by IRC Operators to request a link with a pre-configured server.
    Syntax: CONNECT <servername>

    Note that <servername> should match a server in your configuration file.
    """
    def __init__(self):
        self.command = 'connect'
        self.params = 1
        self.req_flags = 'connect'

    def execute(self, client, recv):
        if 'HTTP/' in recv:
            client.quit('Illegal command')
            return
        name = recv[1]
        if name.lower() == self.ircd.hostname.lower():
            return client.send('NOTICE', '*** Cannot link to own local server.')

        if name not in self.ircd.conf['link']:
            return client.send('NOTICE', '*** Server {} is not configured for linking.'.format(name))

        server = list(filter(lambda s: s.hostname.lower() == name.lower(), self.ircd.servers))

        if server:
            server = server[0]
            if not server.eos and name.lower() in self.ircd.pendingLinks:
                return self.ircd.notice(client, '*** Link to {} is currently being processed.'.format(name))

        if [server for server in set(self.ircd.servers) if server.hostname == name and server.eos]:
            return client.send('NOTICE', '*** Already linked to {}.'.format(name))

        self.ircd.pendingLinks.append(name)
        connectTo(client, self.ircd, name)
