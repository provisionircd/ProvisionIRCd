import os
import sys
import time

def cmd_CYCLE(self, localServer, recv):
    ############################################################################################
    ### This should be at the start of every command, that requires syncing between servers. ###
    ############################################################################################
    try:
        if len(recv) < 2:
            self.sendraw(461, ':CYCLE Not enough parameters')
            return

        for chan in recv[1].split(','):
            channel = list(filter(lambda c: c.name.lower() == chan.lower(), self.channels))
            if not channel:
                self.sendraw(442, '{} :You\'re not on that channel'.format(chan))
                continue

            channel = channel[0]
            p = {'reason': 'Cycling'}
            self.handle('PART', channel.name, params=p)
            self.handle('JOIN', '{}'.format(channel.name))

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        if not localServer.forked:
            print(e)
