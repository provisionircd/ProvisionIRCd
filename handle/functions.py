import base64
import binascii
import string
import socket
from handle.logger import logging


# Author: strlcat - https://github.com/strlcat
def ip_type(ip):
    def isxdigit(s):
        return all(c in string.hexdigits for c in s)

    if isxdigit(ip.replace(':', '')):
        return socket.AF_INET6
    if ip.replace('.', '').isdigit():
        return socket.AF_INET
    return 0


# Author: strlcat - https://github.com/strlcat
def fixup_ip6(ip6):
    ipt = ip_type(ip6)
    if ipt != socket.AF_INET6:
        return ip6
    if ip6[:2] == "::":
        return '0' + ip6
    return ip6


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
    spu = dict(s=1, m=60, h=3600, d=86400, w=604800, M=2592000)
    s = str(s) if isinstance(s, int) else s
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


def make_mask_old(data):
    nick, ident, host = '', '', ''
    nick = data.split('!')[0]
    nicklen = 32
    if nick == '' or '@' in nick or ('.' in nick and '@' not in data):
        nick = '*'
    if len(nick) > nicklen:
        nick = f"*{nick[-20:]}"
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
        ident = f"*{ident[-12:]}"
    try:
        host = data.split('@')[1]
    except:
        if '.' in data:
            try:
                host = ''.join(data.split('@'))
            except:
                host = '*'
    if len(host) > 64:
        host = f"*{host[-64:]}"
    if host == '':
        host = '*'
    result = f"{nick}!{ident}@{host}"
    return result


def make_mask(data):
    # Check if data should be treated as host
    if '!' not in data and '@' not in data and '.' in data:
        nick = '*'
        ident = '*'
        host = data
    else:
        # Assign nick
        nick = data.split('!')[0]
        if not nick or '@' in nick:
            nick = '*'

        # Assign ident
        if '@' in data:
            ident_part = data.split('@')[0]
            if '!' in ident_part:
                ident = ident_part.split('!')[1]
            else:
                ident = ident_part
        else:
            if '!' in data:
                ident = data.split('!')[1]
            else:
                ident = '*'

        # Assign host
        if '@' in data:
            host = data.split('@')[1]
            # # Adjust host if it starts with '!' and ident is '*' or empty
            # if ident in ('', '*') and host.startswith('!'):
            #     host = host[1:]
        else:
            host = '*'

    nick = f"*{nick[-20:]}" if len(nick) > 32 else nick or '*'
    ident = f"*{ident[-12:]}" if len(ident) > 12 else ident or '*'
    host = f"*{host[-64:]}" if len(host) > 64 else host or '*'

    return f"{nick}!{ident}@{host}"


def is_match_old(first, second):
    if not first and not second:
        return True
    if len(first) > 1 and first[0] == '*' and not second:
        return False
    if (len(first) > 1 and first[0] == '?') or (first and second and first[0] == second[0]):
        return is_match(first[1:], second[1:])
    if first and first[0] == '*':
        return is_match(first[1:], second) or is_match(first, second[1:])
    return False


def is_match(first, second):
    if not first:
        return not second
    if first[0] == '*':
        return is_match(first[1:], second) or (second and is_match(first, second[1:]))
    elif second and (first[0] == '?' or first[0] == second[0]):
        return is_match(first[1:], second[1:])
    else:
        return False
