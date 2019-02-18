import os
import sys

def cmd_SETIDENT(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            self = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))
            if not self:
                return        
            ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
            self = self[0]
            recv = recv[1:]
            ident = str(recv[1][:12]).strip()
            self.ident = ident
            localServer.syncToServers(localServer,self.server,':{} SETIDENT {}'.format(self.uid,self.ident))
            return
        
        if 'o' not in self.modes:
            self.sendraw(481,':Permission denied - You are not an IRC Operator')
            return
            
        if len(recv) < 2:
            self.sendraw(461,':SETIDENT Not enough parameters')
            return
            
        ident = str(recv[1][:12]).strip()

        valid = 'abcdefghijklmnopqrstuvwxyz0123456789.-'
        for c in str(ident):
            if c.lower() not in valid:
                ident = ident.replace(c,'')
                #self._send(':{} NOTICE {} :*** Invalid character: {}'.format(localServer.hostname,self.nickname,c))
                #return
        self.ident = ident
        
        self._send(':{} NOTICE {} :*** Your ident is now "{}"'.format(localServer.hostname,self.nickname,self.ident))
        
        localServer.syncToServers(localServer,self.server,':{} SETIDENT {}'.format(self.uid,self.ident))
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
