"""
/tkl (server), /kline, /gline, /zline, /gzline, /sqline, /unsqline and /shun commands
"""

import ipaddress
import re
import time

from handle.functions import valid_expire
from handle.core import Command, Numeric, IRCD, Flag, Stat, Hook, Tkl


def remove_expired_tkl():
    expired = [t for t in Tkl.table if int(t.expire) and int(time.time()) >= int(t.expire)]
    for tkl in expired:
        Tkl.remove(IRCD.me, tkl.type, tkl.ident, tkl.host)


def tkl_to_json():
    result = {}
    for tkl in Tkl.table:
        if tkl.type not in result:
            result[tkl.type] = {}
        result[tkl.type][tkl.mask] = {}
        result[tkl.type][tkl.mask].update(tkl.__dict__)
    return result


def sync_tkl(server):
    for tkl in [tkl for tkl in Tkl.table if tkl.type in Tkl.global_flags()]:
        data = f':{IRCD.me.id} TKL + {tkl.type} {tkl.ident} {tkl.host} {tkl.bantypes} {tkl.set_by} {tkl.expire} {tkl.set_time} :{tkl.reason}'
        server.send([], data)


def make_real_mask(data):
    if "@" not in data:
        return f"*@{data}"
    ident = data.split('@')[0]
    if ident == '':
        ident = '*'
    try:
        host = data.split('@')[1]
    except:
        host = '*'
    if host == '':
        host = '*'
    result = f'{ident}@{host}'
    return result


def cmd_tkl(client, recv):
    tkltype = recv[2]
    ident = recv[3]
    host = recv[4]
    bantypes = recv[5]
    reason = " ".join(recv[9:]).removeprefix(":")
    if recv[1] == '+':
        set_by = recv[6]
        expire = int(recv[7])
        set_time = recv[8]
        Tkl.add(client, tkltype, ident, host, bantypes, set_by, expire, set_time, reason)

    elif recv[1] == '-':
        ident = recv[3]
        host = recv[4]
        Tkl.remove(client, tkltype, ident, host)


class Zline:
    """
    Bans a user from a server (zline) or entire network (gzline) by IP address.
    -
    Syntax: ZLINE <expire> <nick|ip> <reason>
    Example: ZLINE 1d R00T_UK Be gone.
    This will remove and ban user R00T_UK from the server. Ban will expire in 1 day.
    Banning on nickname only works when the user is currently online.
    -
    Expire formats can be: m (minutes), h (hours), d (days), w (weeks), and M (months, 30 days per unit).
    Stacking (like +1d12h) is not yet supported.
    -
    To remove a global Z:line, use -ip as the parameter.
    Example: GZLINE -*@12.34.56.78
    """
    pass


kline_gline_help = """
    Bans a user from a server (kline) or entire network (gline) by hostname.
    -
    Syntax: KLINE <nick|host> <expire> <reason>
    Example: KLINE Kevin 1d Be gone.
    This will remove and ban user Kevin from the server. Ban will expire in 1 day.
    Banning on nickname only works when the user is currently online.
    -
    Expire formats can be: m (minutes), h (hours), d (days), w (weeks), and M (months, 30 days per unit).
    Stacking (like +1d12h) is not supported.
    -
    To remove a global ban, use -host as the parameter.
    Example: GLINE -*@12.34.56.78.prioritytelecom.net
    """


def cmd_line(client, recv):
    if recv[0].lower() == "sqline":
        reason = ' '.join(recv[2:]).removeprefix(":")
        # Server-only command, so 'client'.
        Tkl.add(client, "Q", ident="*", host=recv[1], bantypes='*', set_by=client.name, expire=0, set_time=int(time.time()), reason=reason)
        return
    elif recv[0].lower() == "unsqline":
        Tkl.remove(client, "Q", '*', recv[1])
        return

    if not (cmd_tkl := Tkl.get_flag_of_what(recv[0].lower())):
        IRCD.server_notice(client, f"No flag object found for name: {recv[0]}")
        return
    match recv[0].lower():
        case "kline":
            if not client.has_permission("server-ban:kline"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
        case "gline":
            if not client.has_permission("server-ban:gline"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
        case "zline":
            if not client.has_permission("server-ban:zline:local"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
        case "gzline":
            if not client.has_permission("server-ban:zline:global"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
        case "shun":
            if not client.has_permission("server-ban:shun"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)
        case "eline":
            if not client.has_permission("server-ban:eline"):
                return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if len(recv) == 1:
        if stat := Stat.get("G" if cmd_tkl.flag in Tkl.global_flags() else "g"):
            stat.show(client)
        return

    if recv[1].startswith("-"):
        mask = recv[1].removeprefix("-")
        realmask = make_real_mask(mask)
        if (ident := Tkl.valid_extban(mask)) and len(mask.split(':')) > 1:
            host = mask.split(':')[1]
        else:
            ident, host = realmask.split('@')
        get_mask = Tkl.get_mask(cmd_tkl.flag, ident, host)
        if not Tkl.exists(cmd_tkl.flag, get_mask):
            return IRCD.server_notice(client, f"*** Notice -- No such {cmd_tkl.name}: {get_mask}")
        else:
            Tkl.remove(client.uplink, cmd_tkl.flag, ident, host)

    else:
        if len(recv) < 3:
            return client.sendnumeric(Numeric.ERR_NEEDMOREPARAMS, recv[0].upper())

        bantypes = '*'

        if cmd_tkl.flag == 'E':
            if len(recv) < 4:
                return client.sendnumeric(Numeric.ERR_NEEDMOREPARAMS, recv[0].upper())

            bantypes = ''
            invalid = ''
            for bantype in recv[2]:
                if bantype not in Tkl.valid_eline_flags() or bantype == cmd_tkl.flag:
                    invalid += bantype
                    continue
                bantypes += bantype

            if invalid:
                return IRCD.server_notice(client, f"Invalid bantypes for {cmd_tkl.name}: {invalid}")

            recv[2:] = recv[3:]

        if recv[2] in ['0', '+0']:
            expire = 0
        else:
            if not (expire := valid_expire(recv[2])):
                return IRCD.server_notice(client, "*** Notice -- Invalid expire")
        if len(recv) < 4:
            reason = "No reason specified"
        else:
            reason = " ".join(recv[3:])

        if recv[1].startswith('~') and len(recv[1].split(':')) > 1:
            if ident := Tkl.valid_extban(recv[1]):
                host = recv[1].split(':')[1]
                if not host:
                    return IRCD.server_notice(client, f"Value missing for extban {ident}")
                if expire:
                    expire = int(time.time()) + expire
                if ident == "~certfp:":
                    if not re.match(r"[A-Fa-f0-9]{64}$", host):
                        return IRCD.server_notice(client, f"Invalid certfp. Must be in format [A-Fa-f0-9]{{64}}")

                if ident == "~account:":
                    if host[0].isdigit():
                        errmsg = f"Invalid account name: {host} -- cannot start with number"
                        return IRCD.server_notice(client, errmsg)
                    if host != '*':
                        invalid = []
                        for c in host:
                            if c.lower() not in IRCD.NICKCHARS:
                                if c not in invalid:
                                    invalid.append(c)
                        if invalid:
                            errmsg = f"Invalid account name: {host} -- invalid characters: {','.join(invalid)}"
                            return IRCD.server_notice(client, errmsg)

                set_by = client.fullrealhost
                set_time = int(time.time())
                Tkl.add(client.uplink, flag=cmd_tkl.flag, ident=ident, host=host, bantypes=bantypes, set_by=set_by, expire=expire, set_time=set_time, reason=reason)
            else:
                return IRCD.server_notice(client, f"Invalid extended server ban: {recv[1].split(':')[0]}")
            return

        mask = recv[1]
        if cmd_tkl.flag in "Zz":
            ipmask = mask
            if '@' in mask:
                ipmask = mask.split('@')[1]
            ipmask = ipmask.replace('*', '0')
            try:
                ipaddress.ip_address(ipmask)
            except ValueError:
                return IRCD.server_notice(client, f"Invalid IP address for {cmd_tkl.name}: {mask}")

        if "*" not in recv[1] and "@" not in recv[1] and "." not in recv[1]:
            if not (target := IRCD.find_user(recv[1])):
                return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])
            ident = "*"
            host = target.user.realhost
            mask = f"*@{host}"
        else:
            mask = make_real_mask(recv[1])
            ident, host = mask.split('@')
        if len(mask.replace('*', '')) <= 5 and ('@' in mask or '*' in mask):
            return IRCD.server_notice(client, "*** Notice -- Host range is too small")

        if expire:
            expire = int(time.time()) + expire
        if mask:
            set_by = client.fullrealhost
            set_time = int(time.time())
            Tkl.add(client.uplink, flag=cmd_tkl.flag, ident=ident, host=host, bantypes=bantypes, expire=expire, set_by=set_by, set_time=set_time, reason=reason)


class Shun:
    """
    Limits a users functionality on the network.
    Shunned users can only perform /ADMIN, /MOTD, /PART and /QUIT commands.
    -
    Syntax: SHUN <ident@host> <expire> <reason>
    Example: SHUN Karen 12h Be quiet.

    Shuns Karen for 12 hours.
    Using nicknames as an argument only works when the user is currently online.
    -
    Expire formats can be: m (minutes), h (hours), d (days), w (weeks), and M (months, 30 days per unit).
    Stacking (like +1d12h) is not supported.
    -
    To remove a shun, use -ident@host as the parameter.
    Example: SHUN -*@12.34.56.78.prioritytelecom.net
    """
    pass


def sqline_check_pre_nick(client, newnick):
    if tkl := Tkl.find_tkl_by_mask("Q", newnick) and not client.has_permission("immune:server-ban:qline"):
        client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, newnick, tkl.reason)
        msg = f'*** Q:Line Rejection -- Forbidden nick {newnick} from client {client.ip} {"" if client.name == "*" else f"[Current nick: {client.name}]"}'
        IRCD.send_snomask(client, 'Q', msg)
        return Hook.DENY
    return Hook.CONTINUE


def sqline_check_handshake(client):
    if (tkl := Tkl.is_match(client, "Q")) and not client.has_permission("immune:server-ban:qline"):
        client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, client.name, tkl.reason)
        msg = f'*** Q:Line Rejection -- Forbidden nick {client.name} from client {client.ip} {"" if client.name == "*" else f"[Current nick: {client.name}]"}'
        IRCD.send_snomask(client, 'Q', msg)
        client.name = ''
        return 0
    return 1


def shun_pre_command(client, recv):
    if not client.user:
        return Hook.CONTINUE

    if IRCD.is_except_client("shun", client) or client.has_permission("immune:server-ban:shun"):
        return Hook.CONTINUE

    command = recv[0]
    if command.lower() not in ['admin', 'part', 'quit', 'ping', 'pong', 'motd'] and client.registered and client.is_shunned():
        return Hook.DENY
    return Hook.CONTINUE


def global_tkl_stats(client):
    for t in Tkl.table:
        client.sendnumeric(Numeric.RPL_STATSGLINE, t.type, t.mask, int(t.expire) - int(time.time()) if int(t.expire) else '0', t.set_time, t.set_by, t.reason)


def local_tkl_stats(client):
    for t in [t for t in Tkl.table if t.type not in Tkl.global_flags()]:
        client.sendnumeric(Numeric.RPL_STATSGLINE, t.type, t.mask, int(t.expire) - int(time.time()) if int(t.expire) else '0', t.set_time, t.set_by, t.reason)


# noinspection PyUnboundLocalVariable
def shun_whois(client, whois_client, lines):
    if whois_client.is_shunned() and (shun_tkl := Tkl.is_match(whois_client, 's')) and not whois_client.has_permission("immune:server-ban:shun"):
        line = (Numeric.RPL_WHOISSPECIAL, whois_client.name, "is shunned: " + shun_tkl.reason)
        lines.append(line)


def check_zline(client):
    if client.user and (tkl := Tkl.is_match(client, "Zz")):
        tkl.do_ban(client)


def check_bans(client):
    if client.user and (tkl := Tkl.is_match(client, "Gg")):
        tkl.do_ban(client)
        return Hook.DENY
    return Hook.ALLOW


def init(module):
    Command.add(module, cmd_tkl, "TKL", 3, Flag.CMD_SERVER)
    Command.add(module, cmd_line, "KLINE", 0, Flag.CMD_OPER)
    Command.add(module, cmd_line, "GLINE", 0, Flag.CMD_OPER)
    Command.add(module, cmd_line, "ZLINE", 0, Flag.CMD_OPER)
    Command.add(module, cmd_line, "GZLINE", 0, Flag.CMD_OPER)
    Command.add(module, cmd_line, "SHUN", 0, Flag.CMD_OPER)
    Command.add(module, cmd_line, "SQLINE", 1, Flag.CMD_SERVER)
    Command.add(module, cmd_line, "UNSQLINE", 1, Flag.CMD_SERVER)
    Command.add(module, cmd_line, "ELINE", 0, Flag.CMD_OPER)
    Hook.add(Hook.NEW_CONNECTION, check_zline, 999)
    Hook.add(Hook.PRE_CONNECT, check_bans)
    Hook.add(Hook.IS_HANDSHAKE_FINISHED, sqline_check_handshake)
    Hook.add(Hook.PRE_COMMAND, shun_pre_command)
    Hook.add(Hook.PRE_LOCAL_NICKCHANGE, sqline_check_pre_nick)
    Hook.add(Hook.LOOP, remove_expired_tkl)
    Hook.add(Hook.ACCOUNT_LOGIN, check_bans)
    Hook.add(Hook.SERVER_SYNC, sync_tkl)
    Hook.add(Hook.WHOIS, shun_whois)
    Stat.add(module, global_tkl_stats, "G", "View the all active TKLs")
    Stat.add(module, local_tkl_stats, "g", "View only local active TKLs")
    Tkl.add_flag('k', name="K:Line", what="kline", host_format=1, is_global=0, allow_eline=1)
    Tkl.add_flag('s', name="Shun", what="shun", host_format=1, is_global=0, allow_eline=1)
    Tkl.add_flag('z', name="Z:Line", what="zline", host_format=0, is_global=0, allow_eline=1)
    Tkl.add_flag('E', name="E:Line", what="eline", host_format=1, is_global=0)
    Tkl.add_flag('F', name="Spamfilter", what="spamfilter", host_format=1, is_global=0, allow_eline=1)
    Tkl.add_flag('G', name="G:Line", what="gline", host_format=1, is_global=1, allow_eline=1)
    Tkl.add_flag('Q', name="Q:Line", what="qline", host_format=0, is_global=1, allow_eline=1)
    Tkl.add_flag('Z', name="Z:Line", what="gzline", host_format=1, is_global=1, allow_eline=1)
