#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import datetime
import hashlib
import binascii
import base64
import logging
import logging.handlers

W = '\033[0m'  # white (normal)
R = '\033[31m' # red
R2 = '\033[91m' # bright red
G = '\033[32m' # green
G2 = '\033[92m' # bright green
Y = '\033[33m' # yellow
B = '\033[34m' # blue
P = '\033[35m' # purple

def initlogging(localServer):
    datefile = time.strftime('%Y%m%d')
    loghandlers = [logging.handlers.TimedRotatingFileHandler('logs/logs.txt', when='midnight')]
    if not localServer.forked:
        loghandlers.append(logging.StreamHandler())
    format = '%(asctime)s %(levelname)s [%(module)s]: %(message)s'+W
    logging.basicConfig(level=logging.DEBUG, format=format, datefmt='%Y/%m/%d %H:%M:%S', handlers=loghandlers)
    logging.addLevelName(logging.WARNING, Y+"%s" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, R2+"%s" % logging.getLevelName(logging.ERROR))
    logging.addLevelName(logging.INFO, W+"%s" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.DEBUG, B+"%s" % logging.getLevelName(logging.INFO))

class TKL:
    def check(self, localServer, user, type):
        try:
            if type not in localServer.tkl:
                return
            if type.lower() in 'gz':
                if type in 'gz' and user.server != localServer:
                    return
                ex = False
                for mask in localServer.tkl[type]:
                    host = '{}@{}'.format('*' if type.lower() == 'z' else user.ident, user.ip if type.lower() == 'z' else user.hostname)
                    try:
                        for e in localServer.conf['except']['tkl']:
                            if match(e, host):
                                ex = True
                                break
                    except:
                        pass
                    if match(mask, host) and not ex:
                        if type in 'GZ' and not localServer.tkl[type][mask]['global']:
                            continue
                        if type.lower() in 'gz' and user.server == localServer:
                            ### Local ban on local user.
                            banmsg = localServer.tkl[type][mask]['reason']
                            user.quit('User has been banned from using this server', error=True, banmsg=banmsg)
                        return
        except Exception as ex:
            logging.exception(ex)

    def add(self, localServer, data):
        try:
            data = localServer.parse_command(' '.join(data[3:]))
            tkltype = data[0]
            if tkltype not in localServer.tkl:
                localServer.tkl[tkltype] = {}
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
            user = list(filter(lambda c: c.nickname.lower() == setter.lower(), localServer.users))
            if expire != '0':
                d = datetime.datetime.fromtimestamp(expire).strftime('%a %b %d %Y')
                t = datetime.datetime.fromtimestamp(expire).strftime('%H:%M:%S %Z')
            else:
                d, t = None, None
            if user:
                user = user[0]

            if not no_snotice and (fullmask not in localServer.tkl[tkltype] or fullmask in localServer.tkl[tkltype] and expire != localServer.tkl[tkltype][fullmask]['expire']):
                display_mask = fullmask.split('@')[1] if tkltype == 'Q' else fullmask
                msg = '*** {}TKL {} {} for {} by {} [{}] expires on: {}'.format('Global ' if tkltype in 'GZ' else '', tkltype, 'active' if fullmask not in localServer.tkl[tkltype] else 'updated', display_mask, setter, reason, 'never' if expire == '0' else d+' '+t)
                localServer.snotice('G', msg)

            if fullmask in localServer.tkl[tkltype]:
                del localServer.tkl[tkltype][fullmask]

            localServer.tkl[tkltype][fullmask] = {}
            localServer.tkl[tkltype][fullmask]['ctime'] = ctime
            localServer.tkl[tkltype][fullmask]['expire'] = expire
            localServer.tkl[tkltype][fullmask]['setter'] = setter
            localServer.tkl[tkltype][fullmask]['reason'] = reason
            localServer.tkl[tkltype][fullmask]['global'] = True if tkltype in 'GZQ' else False
            for user in list(localServer.users):
                TKL.check(self, localServer, user, tkltype)

            data = ':{} TKL + {} {} {} {} {} {} :{}'.format(localServer.sid, tkltype, ident, mask, setter, expire, ctime, reason)
            localServer.new_sync(localServer, self, data)
            return

        except Exception as ex:
            logging.exception(ex)

    def remove(self, localServer, data, expire=False):
        try:
            tkltype = data[3]
            ident = data[4]
            mask = data[5]
            fullmask = '{}@{}'.format(ident, mask)
            if fullmask not in localServer.tkl[tkltype] or not fullmask:
                return
            date = '{} {}'.format(datetime.datetime.fromtimestamp(float(localServer.tkl[tkltype][fullmask]['ctime'])).strftime('%a %b %d %Y'), datetime.datetime.fromtimestamp(float(localServer.tkl[tkltype][fullmask]['ctime'])).strftime('%H:%M:%S %Z'))
            date = date.strip()
            if tkltype == 'Q' and ident != 'H':
                display_mask = fullmask.split('@')[1] if tkltype == 'Q' else fullmask
                msg = '*** {}{}TKL {} {} removed (set by {} on {}) [{}]'.format('Expiring ' if expire else '', 'Global ' if tkltype in 'GZ' else '', tkltype, display_mask, localServer.tkl[tkltype][fullmask]['setter'], date, localServer.tkl[tkltype][fullmask]['reason'])
                localServer.snotice('G', msg)
            del localServer.tkl[tkltype][fullmask]
            if tkltype in 'GZQ' and not expire:
                data = ':{} TKL - {} {} {}'.format(localServer.sid, tkltype, ident, mask)
                localServer.new_sync(localServer, self, data)
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
    if 'ssl' in set(server.conf['listen'][str(checkport)]['options']):
        return True
    return False

def _print(txt, server=None):
    write(str(txt), server)

def valid_expire(s):
    spu = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    if s.isdigit():
        return int(s) * 60
    if s[-1] not in spu:
        return False
    return int(s[:-1]) * spu[s[-1]]

def checkSpamfilter(self, localServer, target, filterTarget, msg):
    try:
        if type(self).__name__ == 'Server':
            return
        if 'spamfilter' not in localServer.conf or self.server != localServer or self.ocheck('o', 'override'):
            return False
        for entry in localServer.conf['spamfilter']:
            #t = localServer.conf['spamfilter'][entry]['type']
            action = localServer.conf['spamfilter'][entry]['action']
            if filterTarget in localServer.conf['spamfilter'][entry]['target'] and match(entry.lower(), msg.lower()):
                msg = 'Spamfilter match by {} ({}@{}) matching {} [{} {} {}]'.format(self.nickname, self.ident, self.hostname, entry, filterTarget.upper(), target, msg)
                localServer.snotice('F', msg)
                reason = entry
                if 'reason' in localServer.conf['spamfilter'][entry] and len(localServer.conf['spamfilter'][entry]['reason']) > 0:
                    reason = localServer.conf['spamfilter'][entry]['reason']
                if action == 'block':
                    self.sendraw(404, '{} :Spamfilter match: {}'.format(target, reason))
                    return True
                elif action == 'kill':
                    localServer.handle('kill', '{} :Spamfilter match: {}'.format(self.nickname, reason))

                elif action == 'gzline':
                    duration = localServer.conf['spamfilter'][entry]['duration']
                    duration = valid_expire(duration)
                    data = '+ Z * {} {} {} {} :{}'.format(self.ip, localServer.hostname, str(int(time.time()) + duration), int(time.time()), 'Spamfilter match: {}'.format(reason))
                    localServer.handle('tkl', data)

    except Exception as ex:
        logging.exception(ex)

def update_support(localServer):
    if not hasattr(localServer, 'name'):
        return
    localServer.support = {}
    localServer.server_support = {}
    localServer.support['NETWORK'] = localServer.name
    ext_ban = []
    for module in localServer.modules:
        for function in [function for function in localServer.modules[module][9] if hasattr(function, 'support')]:
            for r in [r for r in function.support]:
                server_support = False
                if type(r) == tuple and len(r) > 1 and r[1]:
                    server_support = True
                    r = r[0]
                param = None
                support = r.split('=')[0]
                if '=' in r:
                    param = r.split('=')[1]
                if support == 'CHANMODES':
                    param = localServer.chmodes_string
                if support == 'PREFIX':
                    param = localServer.chprefix_string
                if support == 'MAXLIST':
                    param = localServer.maxlist_string
                if support == 'EXTBAN':
                    if not ext_ban:
                        ext_ban = param
                    else:
                        ext_ban += param[2:]
                        param = ext_ban

                if support not in localServer.support or support == 'EXTBAN':
                    localServer.support[support] = param
                    #logging.info('Adding support for: {}{}'.format(support, '={}'.format(param) if param else ''))
                if server_support:
                    localServer.server_support[support] = param

    if hasattr(localServer, 'chprefix'):
        chprefix_string = ''
        first = '('
        second = ''
        for key in localServer.chprefix:
            first += key
            second += localServer.chprefix[key]
        first += ')'
        chprefix_string = '{}{}'.format(first, second)
        localServer.chprefix_string = chprefix_string

    if hasattr(localServer, 'channel_modes'):
        chmodes_string = ''
        for t in localServer.channel_modes:
            for m in localServer.channel_modes[t]:
                chmodes_string += m
            chmodes_string += ','
        localServer.chmodes_string = chmodes_string[:-1]

def show_support(self, localServer):
    line = []
    for row in localServer.support:
        row = row
        value = localServer.support[row]
        line.append('{}{}'.format(row, '={}'.format(value) if value else ''))
        if len(line) == 15:
            self.sendraw('005', '{} :are supported by this server'.format(' '.join(line)))
            line = []
            continue
    self.sendraw('005', '{} :are supported by this server'.format(' '.join(line)))

def cloak(localServer, host):
    cloakkey = localServer.conf['settings']['cloak-key']
    key = '{}{}'.format(host, cloakkey)
    hashhost = hashlib.sha512(bytes(key, 'utf-8'))
    hex_dig = hashhost.hexdigest()
    cloak1 = hex(binascii.crc32(bytes(hex_dig[0:32], 'utf-8')) % (1<<32))[2:]
    cloak2 = hex(binascii.crc32(bytes(hex_dig[32:64], 'utf-8')) % (1<<32))[2:]
    if host.replace('.', '').isdigit() or '.ip-' in host:
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

def check_flood(localServer, target):
    try:
        if type(target).__name__ == 'User':
            user = target
            if user.cls:
                sendq = localServer.conf['class'][user.cls]['sendq']
                recvq = localServer.conf['class'][user.cls]['recvq']
            else:
                sendq, recvq = 512, 512

            if not hasattr(user, 'flood_safe') or not user.flood_safe:
                if (len(user.recvbuffer) >= recvq or len(user.sendbuffer) >= sendq) and int(time.time()) - user.signon > 2: #and (user.registered and int(time.time()) - user.signon > 3):
                    ### user.recvbuffer is what the user is sending to the server.
                    flood_type = 'recvq' if len(user.recvbuffer) >= recvq else 'sendq'
                    flood_amount = len(user.recvbuffer) if flood_type == 'recvq' else len(user.sendbuffer)
                    flood_limit = recvq if flood_type == 'recvq' else sendq
                    if user.registered:
                        localServer.snotice('f', '*** Flood1 -- {} ({}@{}) has reached their max {} ({}) while the limit is {}'\
                        .format(user.nickname, user.ident, user.hostname, 'RecvQ' if flood_type == 'recvq' else 'SendQ', flood_amount, flood_limit))
                    user.quit('Excess Flood1', error=True)
                    return

                buffer_len = len(user.recvbuffer.split('\n'))
                max_len = (sendq/2)/10/2
                max_cmds = max_len/2
                if 'o' in user.modes:
                    max_len *= 2
                    max_cmds *= 2

                if (buffer_len >= max_cmds) and (user.registered and int(time.time()) - user.signon > 1):
                    if user.registered:
                        localServer.snotice('f', '*** Flood2 -- {} ({}@{}) has reached their max buffer length ({}) while the limit is {}'\
                        .format(user.nickname, user.ident, user.hostname, buffer_len, max_cmds))
                    user.quit('Excess Flood2', error=True)
                    return

                flood_penalty_treshhold = 1000000
                if int(time.time()) - user.flood_penalty_time > 60:
                    user.flood_penalty = 0
                    user.flood_penalty_time = 0
                if user.flood_penalty >= flood_penalty_treshhold:
                    if user.registered:
                        localServer.snotice('f', '*** Flood -- {} ({}@{}) has reached their max flood penalty ({}) while the limit is {}'\
                        .format(user.nickname, user.ident, user.hostname, user.flood_penalty, flood_penalty_treshhold))
                    user.quit('Excess Flood')
                    return
        else:
            server = target
            if server.cls:
                sendq = localServer.conf['class'][server.cls]['sendq']
                recvq = localServer.conf['class'][server.cls]['recvq']
            else:
                sendq, recvq = 65536, 65536

            if (len(server.recvbuffer) >= recvq or len(server.sendbuffer) >= sendq):
                flood_type = 'recvq' if len(server.recvbuffer) >= recvq else 'sendq'
                flood_amount = len(server.recvbuffer) if flood_type == 'recvq' else len(server.sendbuffer)
                flood_limit = recvq if flood_type == 'recvq' else sendq

                localServer.snotice('f', '*** Flood1-- Server {} has reached their max {} ({}) while the limit is {}'\
                .format(server.hostname, 'RecvQ' if flood_type == 'recvq' else 'SendQ', flood_amount, flood_limit))
                server.quit('Excess Flood')
                return
    except Exception as ex:
        logging.exception(ex)
