#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/motd command
"""

import ircd
import ast
import os
import sys

from handle.functions import _print

@ircd.Modules.commands('motd')
def motd(self, localServer, recv):
    #print(recv)
    try:
        if len(recv) == 1:
            if type(self).__name__ == 'User':
                self.sendraw(375, '{} Message of the Day'.format(localServer.hostname))
                with open(localServer.confdir+'ircd.motd') as f:
                    for line in f.read().split('\n'):
                        self.sendraw(372, ':- {}'.format(line))
                    self.sendraw(376, ':End of Message of the Day.')
            else:
                remoteserver = recv[1].lower()
                #print('Server {} is requesting the MOTD of {}'.format(self.hostname, remoteserver))
                server_exists = [server for server in localServer.servers if server.hostname.lower() == remoteserver]
                if not server_exists:
                    return
                localServer.remote_request[self.hostname] = remoteserver
                with open(localServer.confdir+'ircd.motd') as f:
                    local_motd = []
                    for line in f:
                        local_motd.append(line)
                self._send('MOTD {} {}'.format(localServer.hostname, local_motd))

        else:
            #localServer.remote_request = {}
            remoteserver = recv[1].lower()
            if hasattr(localServer, 'remote_request') and localServer.remote_request:
                if type(self).__name__ == 'Server':
                    #print('Server {} is requesting the MOTD of {}'.format(self.hostname, remoteserver))
                    localServer.remote_request[self.hostname] = remoteserver

                '''
                localServer.remote_request.sendraw(375, '{} Message of the Day'.format(self.hostname))
                lines = ' '.join(recv[1:])
                #print('Remote lines: {}'.format(lines))
                #lines = ast.literal_eval(lines)
                for line in ''.join(lines).split('\n'):
                    localServer.remote_request.sendraw(372, ':- {}'.format(line))
                localServer.remote_request.sendraw(376, ':End of Message of the Day.')
                localServer.remote_request = None
                return
                '''

            server_exists = [server for server in localServer.servers if server.hostname.lower() == remoteserver]
            if not server_exists and remoteserver != localServer.hostname:
                return self.sendraw(402, '{} :No such server'.format(remoteserver))

            if remoteserver == localServer.hostname:
                #print('Server {} is requesting my MOTD'.format(self.hostname))
                send_motd(localServer, self)
                return
            else:
                server = server_exists[0] if server_exists[0].socket else server_exists[0].introducedBy
            #print('Attempting to fetch MOTD from {}: {}'.format(remoteserver, server))
            server._send('MOTD {}'.format(remoteserver))
            #localServer.remote_request = {}


    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

def send_motd(localServer, destination):
    #print('Sending local MOTD to {}'.format(destination))
    with open(localServer.confdir+'ircd.motd') as f:
        local_motd = []
        for line in f:
            local_motd.append(line)
    destination._send('MOTD {} {}'.format(localServer.hostname, local_motd))

def init(self, reload=False):
    self.remote_request = {}
