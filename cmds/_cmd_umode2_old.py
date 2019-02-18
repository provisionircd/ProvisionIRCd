import os
import sys

def cmd_UMODE2(self, localServer, recv):
    try:
        ### :asdf UMODE2 +ot
        if type(self).__name__ == 'Server':
            target = list(filter(lambda u: u.uid == recv[0][1:] or u.nickname == recv[0][1:], localServer.users))[0]
        else:
            self.sendraw(487, ':UMODE2 is a server only command')
            return
        modeset = None
        for m in recv[2]:
            if m in '+-':
                modeset = m
                continue
            if modeset == '+':
                if m not in target.modes:
                    target.modes += m
                if m == '^':
                    target.stealthOn(override=True)

            elif modeset == '-':
                target.modes = target.modes.replace(m, '')
                if m == 'o':
                    target.operflags = []
                    target.swhois = []
                    target.opermodes = ''
                elif m == 's':
                    target.snomasks = ''
                elif m == '^':
                    target.stealthOff(override=True)

        localServer.new_sync(localServer, self, ' '.join(recv))
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)
