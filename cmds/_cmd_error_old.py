import time
import os
import sys

def cmd_ERROR(self, localServer, recv):
    try:
        if type(self).__name__ != 'Server':
            self.sendraw(487,':ERROR is a server only command')
            return
        ### 00B ERROR :msg
        msg = ' '.join(recv[1:])[1:]
        localServer.snotice('s', '*** {}'.format(msg))
        self.quit(msg, silent=True)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        #print(e)