import os
import time
import datetime
import hashlib
import binascii
import base64
import logging
import logging.handlers
import json
from classes.rpl import RPL, ERR

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
R2 = '\033[91m' # bright red
Y = '\033[33m' # yellow

class EnhancedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, filename, when='midnight', interval=1, backupCount=0, encoding=None, delay=0, utc=0, maxBytes=0, backupExpire=0):
        """ This is just a combination of TimedRotatingFileHandler and RotatingFileHandler (adds maxBytes to TimedRotatingFileHandler) """
        logging.handlers.TimedRotatingFileHandler.__init__(self, filename, when, interval, backupCount, encoding, delay, utc)

        self.maxBytes = maxBytes if maxBytes <= 1000*100000 else 1000*100000 # Limit single file to max. 100MB
        self.suffix = '%Y-%m-%d'
        self.filename = filename
        self.backupExpire = backupExpire if backupExpire <= 315569260 else 315569260 # Limit expire to max. 10 years.
        self.backupCount = backupCount if backupCount <= 999 else 999

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.

        we are also comparing times
        """

        if self.stream is None:                 # Delay was set...
            self.stream = self._open()
        if self.maxBytes > 0:                   # Are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  # Due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        if int(time.time()) >= self.rolloverAt:
            return 1
        return 0

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            d = datetime.datetime.today().strftime(self.suffix)
            for i in range(self.backupCount - 1, 0, -1):
                n = "%03d"%(i)
                sfn = self.rotation_filename("%s.%s.%03d" % (self.baseFilename, d, int(n)))
                dfn = self.rotation_filename("%s.%s.%03d" % (self.baseFilename, d, int(n) + 1))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.rotation_filename(self.baseFilename + "." + d + ".001")
            if os.path.exists(dfn):
                os.remove(dfn)
            self.rotate(self.baseFilename, dfn)
            self.deleteOldFiles()
        if not self.delay:
            self.stream = self._open()

        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]
        newRolloverAt = self.computeRollover(currentTime)

        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)

        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval

        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
                if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
                    addend = -3600
                else:           # DST bows out before next rollover, so we need to add an hour
                    addend = 3600
                newRolloverAt += addend
        self.rolloverAt = newRolloverAt

    def deleteOldFiles(self):
        dirName, baseName = os.path.split(self.baseFilename)
        files = os.listdir(dirName)
        for file in [file for file in files if os.path.join(dirName, file) != self.baseFilename]:
            fn = os.path.join(dirName, file)
            if not os.path.isfile(fn):
                continue
            logtimestamp = int(os.path.getmtime(fn)) # Based on last modify.
            diff = int(time.time()) - logtimestamp
            if self.backupExpire and diff > self.backupExpire:
                #print('Removing {} because it is >{} seconds old.'.format(file, diff))
                os.remove(fn)
                continue

            oldest = [os.path.join(dirName, f) for f in files if os.path.isfile(os.path.join(dirName, f))]
            oldest.sort(key=lambda f: int(os.path.getmtime(f)*1000))

            exceed = len(oldest) - self.backupCount
            #print('Exceeding by {} files.'.format(exceed))
            if exceed > 0:
                remove_files = oldest[:exceed]
                #print('Remove {} files:'.format(len(remove_files)))
                for f in remove_files:
                    #print('os.remove({})'.format(f))
                    os.remove(f)

def initlogging(ircd):
    datefile = time.strftime('%Y%m%d')
    if not os.path.exists('logs'):
        os.mkdir('logs')
    filename = 'logs/ircd.log'

    # Removing files >backupCount OR >backupExpire (in seconds)
    loghandlers = [EnhancedRotatingFileHandler(filename, when='midnight', maxBytes=1000*1000, backupCount=30, backupExpire=2629744)] # 2629744 = 1 month

    if not ircd.forked:
        stream = logging.StreamHandler()
        stream.setLevel(logging.DEBUG)
        stream.terminator = '\n'+W
        loghandlers.append(stream)

    format = '%(asctime)s %(levelname)s [%(module)s]: %(message)s'#+W
    logging.basicConfig(level=logging.DEBUG, format=format, datefmt='%Y/%m/%d %H:%M:%S', handlers=loghandlers)
    logging.addLevelName(logging.WARNING, Y+"%s" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, R2+"%s" % logging.getLevelName(logging.ERROR))
    logging.addLevelName(logging.INFO, "%s" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.DEBUG, "%s" % logging.getLevelName(logging.DEBUG))
    l = loghandlers[0]
    logging.debug('Logger initialised with settings:')

    mb_file = l.maxBytes*l.backupCount
    mb_file = mb_file / l.backupCount
    mb_file = float(mb_file) / 1000 / 1000
    mb_file = "%.2f" % mb_file
    logging.debug('maxBytes: {} ({} MB per file)'.format(l.maxBytes, mb_file))

    logging.debug('backupCount: {}'.format(l.backupCount))

    sec = datetime.timedelta(seconds=l.backupExpire)
    d = datetime.datetime(1,1,1) + sec
    logging.debug('backupExpire: {} ({} years, {} months, {} days)'.format(l.backupExpire, d.year-1, d.month-1, d.day-1))

    max_size = l.maxBytes*(l.backupCount+1) # Include base file.
    mb_size = float(max_size) / 1000 / 1000
    mb_size = "%.2f" % mb_size
    logging.debug('Max possible total logs size: {} bytes ({} MB)'.format(max_size, mb_size))

    logging.debug('Logs will rotate log files with interval: {}'.format(l.when))

    if max_size > 1000000000:
        gb_size = float(mb_size) / 1000
        gb_size = "%.2f" % gb_size
        print('{}WARNING: Total log size limit exceeds 1GB: {} GB{}'.format(R, gb_size, W))
        print('Pausing for 5 seconds for visibility...')
        time.sleep(5)


class TKL:
    def check(self, ircd, user, type):
        try:
            if type not in ircd.tkl:
                return
            if type.lower() in 'gz':
                if type in 'gz' and user.server != ircd:
                    return
                ex = False
                for mask in iter(ircd.tkl[type]):
                    host = '{}@{}'.format('*' if type.lower() == 'z' else user.ident, user.ip if type.lower() == 'z' else user.hostname)
                    if 'except' in ircd.conf and 'tkl' in ircd.conf['except']:
                        for e in ircd.conf['except']['tkl']:
                            if match(e, host) and user.server == ircd:
                                ex = True
                                break

                    if match(mask, host) and not ex:
                        if type in 'GZ' and not ircd.tkl[type][mask]['global']:
                            continue
                        if type.lower() in 'gz' and user.server == ircd:
                            ### Local ban on local user.
                            banmsg = ircd.tkl[type][mask]['reason']
                            setter = ircd.tkl[type][mask]['setter']
                            if user.socket:
                                if user.registered:
                                    ircd.notice(user, '*** You are banned from this server: [{}] {}'.format(setter, banmsg))
                                user.sendraw(304, '{}'.format(':[{}] {}'.format(setter, banmsg)))
                            user.quit('User has been banned from using this server', error=True)
                        return
        except Exception as ex:
            logging.exception(ex)

    def add(self, ircd, data):
        try:
            data = ircd.parse_command(' '.join(data[3:]))
            tkltype = data[0]
            if tkltype not in ircd.tkl:
                ircd.tkl[tkltype] = {}
            no_snotice = False
            ident = data[1]
            if tkltype == 'Q' and data[1] == 'H':
                no_snotice = True
            mask = data[2]
            fullmask = '{}@{}'.format(ident, mask)
            setter = data[3].split('!')[0]
            expire = '0' if float(data[4]) == 0 else int(data[4])
            ctime = int(data[5])
            reason = data[6]
            user = list(filter(lambda c: c.nickname.lower() == setter.lower(), ircd.users))
            if expire != '0':
                d = datetime.datetime.fromtimestamp(expire).strftime('%a %b %d %Y')
                t = datetime.datetime.fromtimestamp(expire).strftime('%H:%M:%S %Z')
            else:
                d, t = None, None
            if user:
                user = user[0]

            if not no_snotice and (fullmask not in ircd.tkl[tkltype] or fullmask in ircd.tkl[tkltype] and expire != ircd.tkl[tkltype][fullmask]['expire']):
                display_mask = fullmask.split('@')[1] if tkltype == 'Q' else fullmask
                msg = '*** {}TKL {} {} for {} by {} [{}] expires on: {}'.format('Global ' if tkltype in 'GZ' else '', tkltype, 'active' if fullmask not in ircd.tkl[tkltype] else 'updated', display_mask, setter, reason, 'never' if expire == '0' else d+' '+t)
                ircd.snotice('G', msg)

            if fullmask in ircd.tkl[tkltype]:
                del ircd.tkl[tkltype][fullmask]

            ircd.tkl[tkltype][fullmask] = {}
            ircd.tkl[tkltype][fullmask]['ctime'] = ctime
            ircd.tkl[tkltype][fullmask]['expire'] = expire
            ircd.tkl[tkltype][fullmask]['setter'] = setter
            ircd.tkl[tkltype][fullmask]['reason'] = reason
            ircd.tkl[tkltype][fullmask]['global'] = True if tkltype in 'GZQ' else False
            for user in list(ircd.users):
                TKL.check(self, ircd, user, tkltype)

            if tkltype in 'GZQ':
                data = ':{} TKL + {} {} {} {} {} {} :{}'.format(ircd.sid, tkltype, ident, mask, setter, expire, ctime, reason)
                ircd.new_sync(ircd, self, data)
            save_db(ircd)
            return

        except Exception as ex:
            logging.exception(ex)

    def remove(self, ircd, data, expire=False):
        try:
            tkltype = data[3]
            ident = data[4]
            mask = data[5]
            fullmask = '{}@{}'.format(ident, mask)
            if fullmask not in ircd.tkl[tkltype] or not fullmask:
                return
            date = '{} {}'.format(datetime.datetime.fromtimestamp(float(ircd.tkl[tkltype][fullmask]['ctime'])).strftime('%a %b %d %Y'), datetime.datetime.fromtimestamp(float(ircd.tkl[tkltype][fullmask]['ctime'])).strftime('%H:%M:%S %Z'))
            date = date.strip()
            if ident != 'H': # tkltype == 'Q' and
                display_mask = fullmask.split('@')[1] if tkltype == 'Q' else fullmask
                msg = '*** {}{}TKL {} {} removed (set by {} on {}) [{}]'.format('Expiring ' if expire else '', 'Global ' if tkltype in 'GZ' else '', tkltype, display_mask, ircd.tkl[tkltype][fullmask]['setter'], date, ircd.tkl[tkltype][fullmask]['reason'])
                ircd.snotice('G', msg)
            del ircd.tkl[tkltype][fullmask]
            if tkltype in 'GZQ' and not expire:
                data = ':{} TKL - {} {} {}'.format(ircd.sid, tkltype, ident, mask)
                ircd.new_sync(ircd, self, data)
            save_db(ircd)
        except Exception as ex:
            logging.exception(ex)


def write(line, server=None):
    line = line.replace('[0m', '')
    line = line.replace('[32m', '')
    line = line.replace('[33m', '')
    line = line.replace('[34m', '')
    line = line.replace('[35m', '')
    logging.debug(line)


def match(first, second):
    if not first and not second:
        return True
    if len(first) > 1 and first[0] == '*' and not second:
        return False
    if (len(first) > 1 and first[0] == '?') or (first and second and first[0] == second[0]):
        return match(first[1:], second[1:])
    if first and first[0] == '*':
        return match(first[1:], second) or match(first, second[1:])
    return False


def is_sslport(server,checkport):
    return 'ssl' in set(server.conf['listen'][str(checkport)]['options'])


def _print(txt, server=None):
    write(str(txt), server)


def valid_expire(s):
    spu = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "M": 2592000}
    if s.isdigit():
        return int(s) * 60
    if s[-1] not in spu:
        return False
    return int(s[:-1]) * spu[s[-1]]


def checkSpamfilter(self, ircd, target, filterTarget, msg):
    try:
        if type(self).__name__ == 'Server':
            return
        if 'spamfilter' not in ircd.conf or self.server != ircd or self.ocheck('o', 'override'):
            return False
        for entry in iter(ircd.conf['spamfilter']):
            #t = ircd.conf['spamfilter'][entry]['type']
            action = ircd.conf['spamfilter'][entry]['action']
            if filterTarget in ircd.conf['spamfilter'][entry]['target'] and match(entry.lower(), msg.lower()):
                msg = 'Spamfilter match by {} ({}@{}) matching {} [{} {} {}]'.format(self.nickname, self.ident, self.hostname, entry, filterTarget.upper(), target, msg)
                ircd.snotice('F', msg)
                reason = entry
                if 'reason' in ircd.conf['spamfilter'][entry] and len(ircd.conf['spamfilter'][entry]['reason']) > 0:
                    reason = ircd.conf['spamfilter'][entry]['reason']
                if action == 'block':
                    self.sendraw(404, '{} :Spamfilter match: {}'.format(target, reason))
                    return True
                elif action == 'kill':
                    ircd.handle('kill', '{} :Spamfilter match: {}'.format(self.nickname, reason))

                elif action == 'gzline':
                    duration = ircd.conf['spamfilter'][entry]['duration']
                    duration = valid_expire(duration)
                    data = '+ Z * {} {} {} {} :{}'.format(self.ip, ircd.hostname, str(int(time.time()) + duration), int(time.time()), 'Spamfilter match: {}'.format(reason))
                    ircd.handle('tkl', data)

    except Exception as ex:
        logging.exception(ex)


def update_support(ircd):
    ircd.server_support = {}
    if hasattr(ircd, 'channel_modes'):
        chmodes_string = ''
        for t in ircd.channel_modes:
            for m in ircd.channel_modes[t]:
                chmodes_string += m
            chmodes_string += ','
        ircd.chmodes_string = chmodes_string[:-1]


    if hasattr(ircd, 'chprefix'):
        chprefix_string = ''
        first = '('
        second = ''
        for key in ircd.chprefix:
            first += key
            second += ircd.chprefix[key]
        first += ')'
        chprefix_string = '{}{}'.format(first, second)
        ircd.chprefix_string = chprefix_string

    if not hasattr(ircd, 'name'):
        return
    ircd.support = {}
    ircd.server_support = {}
    ircd.support['NETWORK'] = ircd.name
    ext_ban = []

    core_classes = ircd.command_class + ircd.user_mode_class + ircd.channel_mode_class
    for mod in [mod for mod in core_classes if hasattr(mod, 'support') and mod.support]: # if hasattr(mod, 'support') and mod.support]:
        # This is a list containing tuples.
        # Each list entry contains support info as a tuple.
        # If a tuple consists of 2 items, it has a param.
        for entry in mod.support:
            # entry is a tuple.
            support = entry[0]
            if support[-1] == '=':
                support = support[:-1]
            param = None
            if len(entry) == 2:
                param = str(entry[1])

            if support == 'CHANMODES':
                param = ircd.chmodes_string
            if support == 'PREFIX':
                param = ircd.chprefix_string
            if support == 'MAXLIST':
                param = ircd.maxlist_string
            if support == 'EXTBAN':
                if not ext_ban:
                    ext_ban = param
                else:
                    ext_ban += param[2:]
                    param = ext_ban

            if support not in ircd.support or support == 'EXTBAN':
                ircd.support[support] = param

            if hasattr(mod, 'server_support') and mod.server_support:
                ircd.server_support[support] = param

    # Decorate method, EXTBAN does not hook a command or mode so we have to check it this way.
    for module in ircd.modules:
        for function in iter([function for function in ircd.modules[module][4] if hasattr(function, 'support')]):
            for r in [r for r in function.support]:
                server_support = False
                if type(r) == tuple and len(r) > 1 and r[1]:
                    server_support = True
                    r = r[0]
                param = None
                support = r.split('=')[0]
                if '=' in r:
                    param = str(r.split('=')[1])
                if support == 'CHANMODES':
                    param = ircd.chmodes_string
                if support == 'PREFIX':
                    param = ircd.chprefix_string
                if support == 'MAXLIST':
                    param = ircd.maxlist_string
                if support == 'EXTBAN':
                    if not ext_ban:
                        ext_ban = param
                    else:
                        ext_ban += param[2:]
                        param = ext_ban

                if support not in ircd.support or support == 'EXTBAN':
                    ircd.support[support] = param
                    #logging.info('Adding support for: {}{}'.format(support, '={}'.format(param) if param else ''))
                if server_support:
                    ircd.server_support[support] = param


def show_support(client, ircd):
    line = []
    for row in ircd.support:
        value = ircd.support[row]
        line.append('{}{}'.format(row, '={}'.format(value) if value else ''))
        if len(line) == 15:
            client.sendraw(RPL.ISUPPORT, '{} :are supported by this server'.format(' '.join(line)))
            line = []
            continue
    client.sendraw(RPL.ISUPPORT, '{} :are supported by this server'.format(' '.join(line)))


def cloak(client):
    """
    host = received hostname, depending on resolve settings. Can either be IP or realhost.
    """

    ircd = client.server
    host = client.hostname
    ip = client.ip

    # If the resolved hostname strongly represents an IP address, treat it as such.
    static = ['static.kpn.net']
    if host in static or '.ip-' in host:
        host = ip

    cloakkey = ircd.conf['settings']['cloak-key']
    key = '{}{}'.format(host, cloakkey)
    hashhost = hashlib.sha512(bytes(key, 'utf-8'))
    hex_dig = hashhost.hexdigest()
    cloak1 = hex(binascii.crc32(bytes(hex_dig[0:32], 'utf-8')) % (1<<32))[2:]
    cloak2 = hex(binascii.crc32(bytes(hex_dig[32:64], 'utf-8')) % (1<<32))[2:]

    if host.replace('.', '').isdigit():
        cloak3 = hex(binascii.crc32(bytes(hex_dig[64:96], 'utf-8')) % (1<<32))[2:]
        cloakhost = cloak1+'.'+cloak2+'.'+cloak3+'.IP'
        return cloakhost
    c = 0
    for part in host.split('.'):
        c += 1
        if part.replace('-', '').isalpha():
            break
    if c == 1:
        c += 1
    host = '.'.join(host.split('.')[c-1:])
    cloakhost = cloak1+'.'+cloak2+'.'+host
    return cloakhost


def IPtoBase64(ip):
    if ip == '*':
        return
    try:
        ip = ip.split('.')
        s = ''
        for g in ip:
            b = "%X" % int(g)
            if len(b) == 1:
                b = '0'+b
            s += b
        result = binascii.unhexlify(s.rstrip().encode('utf-8'))
        binip = base64.b64encode(result)
        binip = binip.decode()
        return binip
    except Exception as ex:
        logging.exception(ex)


def Base64toIP(base):
    try:
        ip = []
        string = base64.b64decode(base)
        hex_string = binascii.hexlify(string).decode()
        for e in range(0, len(hex_string), 2):
            a = hex_string[e:e+2]
            num = int(a, 16)
            ip.append(str(num))
        ip = '.'.join(ip)
        return ip
    except Exception as ex:
        logging.exception(ex)


def check_flood(ircd, target):
    try:
        if type(target).__name__ == 'User':
            user = target
            flood_safe = True if hasattr(user, 'flood_safe') and user.flood_safe else False
            if user.cls:
                sendq = ircd.conf['class'][user.cls]['sendq']
                recvq = ircd.conf['class'][user.cls]['recvq']
            else:
                sendq, recvq = 512, 512

            if (len(user.recvbuffer) >= recvq or len(user.sendbuffer) >= sendq) and int(time.time()) - user.signon > 2 and not flood_safe: #and (user.registered and int(time.time()) - user.signon > 3):
                ### user.recvbuffer is what the user is sending to the server. (what the server receives)
                flood_type = 'recvq' if len(user.recvbuffer) >= recvq else 'sendq'
                flood_amount = len(user.recvbuffer) if flood_type == 'recvq' else len(user.sendbuffer)
                flood_limit = recvq if flood_type == 'recvq' else sendq
                if user.registered:
                    ircd.snotice('f', '*** Flood1 -- {} ({}@{}) has reached their max {} ({}) while the limit is {}'\
                    .format(user.nickname, user.ident, user.hostname, 'RecvQ' if flood_type == 'recvq' else 'SendQ', flood_amount, flood_limit))
                user.quit('Excess Flood1')
                return
            else:
                #if flood_safe:
                #    logging.debug('Flood_safe for {}: {}'.format(user, '<< '+user.sendbuffer if user.sendbuffer else '>> '+user.recvbuffer))
                buffer_len = len(user.recvbuffer.split('\n'))
                max_len = recvq/10
                max_cmds = max_len/10
                if 'o' in user.modes:
                    max_cmds *= 5

                if (buffer_len >= max_cmds) and (user.registered and int(time.time()) - user.signon > 1):
                    if user.registered:
                        ircd.snotice('f', '*** Buffer Flood -- {} ({}@{}) has reached their max buffer length ({}) while the limit is {}'\
                        .format(user.nickname, user.ident, user.hostname, buffer_len, max_cmds))
                    logging.debug('Flood buffer: {}'.format(user.recvbuffer))
                    user.quit('Excess Flood2')
                    return

                flood_penalty_treshhold = 1000000 if 'o' not in user.modes else 10000000
                if int(time.time()) - user.flood_penalty_time > 60:
                    user.flood_penalty = 0
                    user.flood_penalty_time = 0
                if user.flood_penalty >= flood_penalty_treshhold:
                    if user.registered and not flood_safe:
                        ircd.snotice('f', '*** Flood -- {} ({}@{}) has reached their max flood penalty ({}) while the limit is {}'\
                        .format(user.nickname, user.ident, user.hostname, user.flood_penalty, flood_penalty_treshhold))
                    user.quit('Excess Flood')
                    return
        else:
            server = target
            if server.cls:
                sendq = ircd.conf['class'][server.cls]['sendq']
                recvq = ircd.conf['class'][server.cls]['recvq']
            else:
                sendq, recvq = 65536, 65536

            if (len(server.recvbuffer) >= recvq or len(server.sendbuffer) >= sendq):
                flood_type = 'recvq' if len(server.recvbuffer) >= recvq else 'sendq'
                flood_amount = len(server.recvbuffer) if flood_type == 'recvq' else len(server.sendbuffer)
                flood_limit = recvq if flood_type == 'recvq' else sendq

                ircd.snotice('f', '*** Flood1 -- Server {} has reached their max {} ({}) while the limit is {}'\
                .format(server.hostname, 'RecvQ' if flood_type == 'recvq' else 'SendQ', flood_amount, flood_limit))
                server.quit('Excess Flood')
                return
    except Exception as ex:
        logging.exception(ex)


def save_db(ircd):
    perm_chans = {}
    current_perm = {}
    try:
        with open(ircd.rootdir+'/db/chans.db') as f:
            current_perm = f.read().split('\n')[0]
            current_perm = json.loads(current_perm)
    except Exception as ex:
        pass
    for chan in iter([chan for chan in iter(ircd.channels) if 'P' in chan.modes]):
        perm_chans[chan.name] = {}
        perm_chans[chan.name]['creation'] = chan.creation
        perm_chans[chan.name]['modes'] = chan.modes
        perm_chans[chan.name]['bans'] = chan.bans
        perm_chans[chan.name]['invex'] = chan.invex
        perm_chans[chan.name]['excepts'] = chan.excepts
        perm_chans[chan.name]['modeparams'] = ircd.chan_params[chan]
        perm_chans[chan.name]['topic'] = [] if not chan.topic else [chan.topic, chan.topic_author, chan.topic_time]

    if perm_chans and current_perm != perm_chans:
        logging.debug('Perm channels data changed, updating file... If this message gets spammed, you probably have another instance running.')
        with open(ircd.rootdir+'/db/chans.db', 'w+') as f:
            json.dump(perm_chans, f)

    current_tkl = {}
    try:
        with open(ircd.rootdir+'/db/tkl.db') as f:
            current_tkl = f.read().split('\n')[0]
            current_tkl = json.loads(current_tkl)
    except:
        pass
    if ircd.tkl and current_tkl != ircd.tkl:
        logging.debug('TKL data changed, updating file... If this message gets spammed, you probably have another instance running.')
        with open(ircd.rootdir+'/db/tkl.db', 'w+') as f:
            json.dump(ircd.tkl, f)


def make_mask(ircd, data):
    if not data:
        return
    nick, ident, host = '', '', ''
    nick = data.split('!')[0]
    if nick == '' or '@' in nick or ('.' in nick and '@' not in data):
        nick = '*'
    if len(nick) > ircd.nicklen:
        nick = '*{}'.format(nick[-20:])
    try:
        if '@' in data:
            ident = data.split('@')[0]
            if '!' in ident:
                ident = data.split('@')[0].split('!')[1]
        else:
            ident = data.split('!')[1].split('@')[0]
    except:
        ident = '*'
    if ident == '':
        ident = '*'
    if len(ident) > 12:
        ident = '*{}'.format(ident[-12:])
    try:
        host = data.split('@')[1]
    except:
        if '.' in data:
            try:
                host = ''.join(data.split('@'))
            except:
                host = '*'
    if len(host) > 64:
        host = '*{}'.format(host[-64:])
    if host == '':
        host = '*'
    result = '{}!{}@{}'.format(nick, ident, host)
    return result
