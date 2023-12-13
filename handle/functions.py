import base64
import binascii
import time
from handle.logger import logging


def reverse_ip(ip):
    x = 3
    revip = ''
    while 1:
        if revip:
            revip = revip + '.' + ip.split('.')[x]
        else:
            revip = ip.split('.')[x]
        if x == 0:
            break
        x -= 1
    return revip


def valid_expire(s):
    spu = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "M": 2592000}
    if type(s) == int:
        s = str(s)
    if s.isdigit():
        return int(s) * 60
    if s[-1] not in spu:
        return False
    try:
        return int(s[:-1]) * spu[s[-1]]
    except ValueError:
        return False


def IPtoBase64(ip):
    if ip == '*':
        return
    try:
        ip = ip.split('.')
        s = ''
        for g in ip:
            b = "%X" % int(g)
            if len(b) == 1:
                b = '0' + b
            s += b
        result = binascii.unhexlify(s.rstrip().encode("utf-8"))
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
            a = hex_string[e:e + 2]
            num = int(a, 16)
            ip.append(str(num))
        ip = '.'.join(ip)
        return ip
    except Exception as ex:
        logging.exception(ex)


def make_mask(data):
    nick, ident, host = '', '', ''
    nick = data.split('!')[0]
    nicklen = 32
    if nick == '' or '@' in nick or ('.' in nick and '@' not in data):
        nick = '*'
    if len(nick) > nicklen:
        nick = f'*{nick[-20:]}'
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
        ident = f'*{ident[-12:]}'
    try:
        host = data.split('@')[1]
    except:
        if '.' in data:
            try:
                host = ''.join(data.split('@'))
            except:
                host = '*'
    if len(host) > 64:
        host = f'*{host[-64:]}'
    if host == '':
        host = '*'
    result = f'{nick}!{ident}@{host}'
    return result


def is_match(first, second):
    if not first and not second:
        return True
    if len(first) > 1 and first[0] == '*' and not second:
        return False
    if (len(first) > 1 and first[0] == '?') or (first and second and first[0] == second[0]):
        return is_match(first[1:], second[1:])
    if first and first[0] == '*':
        return is_match(first[1:], second) or is_match(first, second[1:])
    return False
