import os
import sys

def cmd_SVSKILL(self, localServer, recv):
    try:
        if type(self).__name__ != 'Server':
            return
        ### Servers can override kill any time.
        self = list(filter(lambda u: u.nickname.lower() == recv[0][1:].lower() or u.uid.lower() == recv[0][1:].lower(), localServer.users))
        if not self:
            ### Maybe it is a server?
            self = list(filter(lambda s: s.hostname.lower() == recv[0][1:].lower() or s.sid.lower() == recv[0][1:].lower(), localServer.servers))
            if not self:
                return
            else:
                self = self[0]
                sourceID = self.sid
        else:
            self = self[0]
            sourceID = self.uid

        recv = recv[1:]
        target = list(filter(lambda u: u.nickname.lower() == recv[1].lower() or u.uid.lower() == recv[1].lower(), localServer.users))
        if not target:
            return
        reason = ' '.join(recv[2:])[1:]

        data = ':{} SVSKILL {} :{}'.format(sourceID,target[0].uid,reason)

        if target[0].server != localServer:
            target[0].server._send(data)

        target[0].quit(reason)
        return

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        #print(e)
