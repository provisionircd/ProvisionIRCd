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


def reverse_ip(ip: str) -> str:
    octets = ip.split('.')
    return '.'.join(octets[::-1])


def valid_expire(s: str) -> bool | int:
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


def ip_to_base64(ip: str) -> str | None:
    if ip == '*':
        return None
    try:
        hex_octets = [f"{int(octet):02X}" for octet in ip.split('.')]
        hex_str = ''.join(hex_octets)
        binary_data = binascii.unhexlify(hex_str)
        return base64.b64encode(binary_data).decode()
    except (ValueError, binascii.Error) as ex:
        logging.exception(f"Error encoding IP address {ip}: {ex}")
        return None


def base64_to_ip(base: str):
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


def make_mask(data: str) -> str:
    # Check if data should be treated as host
    if '!' not in data and '@' not in data and ('.' in data or ':' in data):
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

        if '@' in data:
            host = data.split('@')[1]
        else:
            host = '*'

    nick = f"*{nick[-20:]}" if len(nick) > 32 else nick or '*'
    ident = f"*{ident[-12:]}" if len(ident) > 12 else ident or '*'
    host = f"*{host[-64:]}" if len(host) > 64 else host or '*'

    return f"{nick}!{ident}@{host}"


def is_match(first: str, second: str, memo=None) -> bool:
    if memo is None:
        memo = {}

    key = (first, second)
    if key in memo:
        return memo[key]

    if not first:
        result = not second
    elif first[0] == '*':
        result = is_match(first[1:], second, memo) or (second and is_match(first, second[1:], memo))
    elif second and (first[0] == '?' or first[0] == second[0]):
        result = is_match(first[1:], second[1:], memo)
    else:
        result = False

    memo[key] = result
    return result
