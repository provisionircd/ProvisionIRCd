def cmd_MOTD(self, localServer, recv):
    print(recv)
    if len(recv) == 1:
        if type(self).__name__ == 'User':
            self.sendraw(375, '{} Message of the Day'.format(localServer.hostname))
            with open(localServer.confdir+'ircd.motd') as f:
                for line in f:
                    self.sendraw(372, ':- {}'.format(line))
                self.sendraw(376, ':End of Message of the Day.')
        else:
            print('Remote server {} requested our motd.'.format(self.hostname))
    else:
        remoteserver = recv[1].lower()
        print('Finding {}'.format(remoteserver))
        sock = [server for server in localServer.servers if server.hostname.lower() == remoteserver and server.socket]
        if not sock:
            ### Not a direct link
            pass
        else:
            sock = sock[0]
            print('Found {}'.format(sock))
            sock._send('MOTD')
            print('Requested remote MOTD')