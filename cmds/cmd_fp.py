def cmd_FP(self, localServer, recv):
    fp = self.socket.getpeercert()
    self._send(':{} NOTICE {} :*** SSL fingerprint: {}'.format(self.server.hostname, self.nickname, fp))