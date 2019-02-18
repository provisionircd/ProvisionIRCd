import os
import sys
import time

def cmd_PONG(self, localServer, recv):
    try:
        if type(self).__name__ == 'Server':
            ### Sent: :00B PONG services.dev.provisionweb.org dev.provisionweb.org
            #print('PONG received for {}, ping reset.'.format(recv[0][1:]))
            source = list(filter(lambda s: s.sid == recv[0][1:] or s.hostname == recv[0][1:], localServer.servers))[0]
            source.ping = int(time.time())

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        print(e)
        