import time
import datetime
import os
import sys

def match(first, second):
    if len(first) == 0 and len(second) == 0:
        return True
    if len(first) > 1 and first[0] == '*' and len(second) == 0:
        return False
    if (len(first) > 1 and first[0] == '?') or (len(first) != 0
        and len(second) !=0 and first[0] == second[0]):
            return match(first[1:],second[1:]);
    if len(first) !=0 and first[0] == '*':
        return match(first[1:],second) or match(first,second[1:])
    return False

class TKL:
    def check(self, localServer, user, type):
        if type not in localServer.tkl:
            return
        if type.lower() in 'gz':
            if type in 'gz' and user.server != localServer:
                return
            ex = False
            for mask in localServer.tkl[type]:
                host = '{}@{}'.format('*' if type.lower() == 'z' else user.ident,user.ip if type.lower() == 'z' else user.hostname)
                try:
                    for e in localServer.conf['except']['tkl']:
                        if match(e,host):
                            ex = True
                            break
                except:
                    pass
                if match(mask,host) and not ex:
                    if type in 'GZ' and not localServer.tkl[type][mask]['global']:
                        continue
                    if type.lower() in 'gz' and user.server == localServer:
                        ### Local ban on local user.
                        banmsg = localServer.tkl[type][mask]['reason']
                        user.quit('User has been banned from using this server', error=True, banmsg=banmsg)
                    return

    def add(self, localServer ,data):
        try:
            data = localServer.parse_command(' '.join(data[3:]))
            tkltype = data[0]
            if tkltype not in localServer.tkl:
                localServer.tkl[tkltype] = {}
            if tkltype.lower() in 'gz':
                mask = '{}@{}'.format(data[1],data[2])
                setter = data[3].split('!')[0]
                expire = '0' if float(data[4]) == 0 else int(data[4])
                ctime = int(data[5])
                reason = data[6]
            elif tkltype.lower() == 'q':
                mask = data[2]
                setter = data[3]
                expire = '0' if float(data[4]) == 0 else int(data[4])
                ctime = int(data[5])
                reason = data[6]
            else:
                return
            user = list(filter(lambda c: c.nickname.lower() == setter.lower(), localServer.users))
            if expire != '0':
                d = datetime.datetime.fromtimestamp(expire).strftime('%a %b %d %Y')
                t = datetime.datetime.fromtimestamp(expire).strftime('%H:%M:%S %Z')
            else:
                d, t = None, None
            if user:
                user = user[0]

            msg = '*** {}TKL {} {} for {} by {} [{}] expires on: {}'.format('Global ' if tkltype in 'GZ' else '', tkltype,'active' if mask not in localServer.tkl[tkltype] else 'updated', mask, setter, reason, 'never' if expire == '0' else d+' '+t)
            localServer.snotice('G', msg)

            if mask in localServer.tkl[tkltype]:
                del localServer.tkl[tkltype][mask]

            localServer.tkl[tkltype][mask] = {}
            localServer.tkl[tkltype][mask]['ctime'] = ctime
            localServer.tkl[tkltype][mask]['expire'] = expire
            localServer.tkl[tkltype][mask]['setter'] = setter
            localServer.tkl[tkltype][mask]['reason'] = reason
            localServer.tkl[tkltype][mask]['global'] = True if tkltype in 'GZQ' else False
            for user in list(localServer.users):
                TKL.check(self, localServer, user, tkltype)
            if tkltype in 'GZ':
                data = ':{} TKL + {} {} {} {} {} {} :{}'.format(localServer.sid, tkltype, mask.split('@')[0], mask.split('@')[1], setter, expire, ctime, reason)
                localServer.syncToServers(localServer, self, data)
            elif tkltype == 'Q':
                data = ':{} TKL + {} * {} {} {} {} :{}'.format(localServer.sid, tkltype, mask, setter, expire, ctime, reason)
                localServer.syncToServers(localServer, self, data)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
            print(e)

    def remove(self, localServer, data, expire=False):
        try:
            ### Me:     :002 TKL - Z * * d74f:4000:fc7f:0:203b:eb94:657f:0
            ### Unreal: ?
            tkltype = data[3]
            if tkltype.lower() in 'gz':
                ### Changed 5 to 4.
                mask = '{}@{}'.format(data[4],data[5])
            elif tkltype.lower() == 'q':
                mask = data[5]

            if mask not in localServer.tkl[tkltype]:
                ### TKL has already been removed locally.
                return
            date = '{} {}'.format(datetime.datetime.fromtimestamp(float(localServer.tkl[tkltype][mask]['ctime'])).strftime('%a %b %d %Y'), datetime.datetime.fromtimestamp(float(localServer.tkl[tkltype][mask]['ctime'])).strftime('%H:%M:%S %Z'))
            date = date.strip()

            msg = '*** {}{}TKL {} {} removed (set by {} on {}) [{}]'.format('Expiring ' if expire else '','Global ' if tkltype in 'GZ' else '', tkltype, mask, localServer.tkl[tkltype][mask]['setter'], date, localServer.tkl[tkltype][mask]['reason'])
            localServer.snotice('G', msg)
            del localServer.tkl[tkltype][mask]

            if tkltype in 'GZQ' and self.eos:
                ### Need to fix that mask shit for Q.
                data = ':{} TKL - {} {} {}'.format(localServer.sid, tkltype, mask.split('@')[0], mask.split('@')[1])
                localServer.syncToServers(localServer, self, data)
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
            #print(e)

def cmd_TKL(self, localServer, recv):
    #print(recv)
    try:
        if type(self).__name__ != 'Server':
            return
        if recv[2] == '+':
            TKL.add(self, localServer, recv)
            ### TKL add.
        elif recv[2] == '-':
            TKL.remove(self, localServer, recv)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        #print(e)

