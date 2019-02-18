import time
import os
import sys
import datetime

def cmd_WHOWAS(self, localServer, recv):
    try:
        if len(recv) < 2:
            self.sendraw(431,':No nickname given')
            return
            
        isWhowas = False
            
        for nick in localServer.whowas:
            if nick.lower() == recv[1].lower():
                isWhowas = True
                for info in localServer.whowas[nick]:
                    ident = info['ident']
                    cloakhost = info['cloakhost']
                    realname = info['realname']
                    hostname = info['hostname']
                    ip = info['ip']
                    signoff = int(info['signoff'])
                    d = datetime.datetime.fromtimestamp(signoff).strftime('%a %b %d')
                    t = datetime.datetime.fromtimestamp(signoff).strftime('%H:%M:%S %Z').strip()
                    y = datetime.datetime.fromtimestamp(signoff).strftime('%Y')
                    server = info['server']
                    self.sendraw(314,'{} {} {} * :{}'.format(nick,ident,cloakhost,realname))
                    if 'o' in self.modes:
                        self.sendraw(378,'{} :connected from *@{} {}'.format(nick,hostname,ip))
                    self.sendraw(312,'{} {} :{} {} {}'.format(nick,server,d,t,y))
                    
        if not isWhowas:
            self.sendraw(406, '{} :There was no such nickname'.format(recv[1]))
            self.sendraw(369,'{} :End of /WHOWAS list.'.format(recv[1]))
            return
            
        self.sendraw(369,'{} :End of /WHOWAS list.'.format(recv[1]))
        
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__,fname,exc_tb.tb_lineno,exc_obj)
        print(e)