import os, sys

def cmd_QUIT(self, localServer, recv, showPrefix=True):
    try:
        ### This should be at the start of every command, where source = where the commsnd came from.
        if type(self).__name__ == 'Server':
            showPrefix = False
            self = list(filter(lambda u: u.uid == recv[0][1:], localServer.users))
            if self == []:
                ### User is already disconnected.
                return
            else:
                self = self[0]
                
            recv = recv[1:]

        if len(recv) > 1:
            reason = ' '.join(recv[1:][:128])
            if reason.startswith(':'):
                reason = reason[1:]
        else:
            reason = self.nickname
            
        try:
            quitprefix = str(localServer.conf['settings']['quitprefix']).strip()

            if quitprefix.endswith(':'):
                quitprefix = quitprefix[:-1]
        except:
            quitprefix = 'Quit'

        if 'static-quit' in localServer.conf['settings'] and localServer.conf['settings']['static-quit']:
            reason = localServer.conf['settings']['static-quit']
            
        reason = '{}{}'.format(quitprefix+': ' if self.server == localServer and showPrefix else '',reason)
        self.quit(reason)
        
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        if not localServer.forked:
            print(e)
        