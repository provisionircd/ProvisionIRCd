"""
/tkl (server), /kline, /gline, /zline, /gzline, /sqline, /unsqline and /shun commands
"""

from datetime import datetime
import ipaddress
import logging
import re
import time
from dataclasses import dataclass

from handle.functions import valid_expire, is_match
from handle.logger import logging
from handle.core import IRCD, Command, Numeric, Flag, Stat, Hook


@dataclass
class TklFlag:
    flag: str = ''
    name: str = ''
    what: str = ''
    host_format: int = 1
    is_global: int = 0
    allow_eline: int = 1
    is_extended: int = 0


class Tkl:
    table = []
    flags = []

    ext_names = {"~account:": "~account:", "~a:": "~account:", "~certfp:": "~certfp:", "~S:": "~certfp:", }

    def __init__(self, client, _type, ident, host, bantypes, expire, set_by, set_time, reason):
        self.client = client
        self.type = _type
        self.ident = ident
        self.host = host
        self.bantypes = bantypes
        self.expire = expire
        self.set_by = set_by
        self.set_time = set_time
        self.reason = reason

    @staticmethod
    def add_flag(flag: str, name: str, what: str, host_format: int, is_global: int, allow_eline: int = 0, is_extended: int = 0):
        """
        :param host_format:         1 = ident@host, 0 = raw (only host part)
                                    Determine the format shown in server notices.
                                    Raw is generally only used for Q:lines and extended server bans
                                    so that it doesn't show it as *@[...].
        """

        tkl_flag = TklFlag(flag, name, what, host_format, is_global, allow_eline, is_extended)
        Tkl.flags.append(tkl_flag)

    @staticmethod
    def get_flag_of_what(what: str):
        return next((tkl for tkl in Tkl.flags if tkl.what == what), 0)

    @staticmethod
    def get_flags_host_format():
        return ''.join([tkl.flag for tkl in Tkl.flags if tkl.host_format])

    @staticmethod
    def global_flags():
        return ''.join([t.flag for t in Tkl.flags if t.is_global])

    @staticmethod
    def valid_flags():
        return ''.join([t.flag for t in Tkl.flags])

    @staticmethod
    def valid_eline_flags():
        return ''.join([t.flag for t in Tkl.flags if t.allow_eline])

    @property
    def name(self):
        return next((t.name for t in Tkl.flags if t.flag == self.type), None)

    def is_extended(self):
        return 1 if self.ident in Tkl.ext_names else 0

    @property
    def mask(self):
        return Tkl.get_mask(self.type, self.ident, self.host)

    @staticmethod
    def get_mask(tkltype, ident, host):
        if ident in Tkl.ext_names:
            return f"{Tkl.ext_names[ident]}{host}"
        return f"{ident}@{host}" if tkltype in Tkl.get_flags_host_format() else host

    @staticmethod
    def exists(tkltype, mask):
        for tkl in Tkl.table:
            if tkl.type == tkltype and tkl.mask == mask:
                return tkl
        return 0

    @staticmethod
    def valid_extban(mask):
        """ Returns the converted ident if this mask is a valid extban, otherwise 0. """
        ident = mask.split(':')[0] + ':'
        if ident in Tkl.ext_names:
            return Tkl.ext_names[ident]
        return 0

    @property
    def is_global(self):
        return self.type in Tkl.global_flags()

    @staticmethod
    def add(client, flag, ident, host, bantypes, set_by, expire, set_time, reason, silent=0):
        """
        client:     Source performing the add.
        bantypes:   Only applicable with /eline. Specifies which bantypes to except.
        """

        if flag not in Tkl.valid_flags():
            return logging.warning(f"Attempted to add non-existing TKL {flag} from {client.name}")

        mask = Tkl.get_mask(flag, ident, host)
        update, exists = 0, 0

        if tkl := Tkl.exists(flag, mask):
            exists = 1
            if int(expire) != int(tkl.expire) or tkl.reason != reason:
                update, tkl.expire, tkl.reason, tkl.bantypes = 1, expire, reason, bantypes
        else:
            expire = int(expire)
            tkl = Tkl(client, flag, ident, host, bantypes, expire, set_by, set_time, reason)
            Tkl.table.append(tkl)
            if flag in "kGzZ" and (matches := Tkl.find_matches(tkl)):
                for c in matches:
                    tkl.do_ban(c)

        expire_string = f"{'never' if expire == 0 else datetime.fromtimestamp(expire).strftime('%a %b %d %Y %H:%M:%S %Z')}"
        bantypes = '' if bantypes == '*' else bantypes
        bt_string = f" [{bantypes}]" if bantypes else ''

        if (client.user and (client.uplink == IRCD.me or client.uplink.server.synced)) or (
                client == IRCD.me or client.server.synced) and not silent:
            msg = (f"*** {'Global ' if tkl.is_global else ''}{tkl.name}{bt_string} {'active' if not update and not exists else 'updated'} "
                   f"for {tkl.mask} by {set_by} [{reason}] expires on: {expire_string}")
            IRCD.log(client, "info", "tkl", "TKL_ADD", msg, sync=not tkl.is_global)

        if tkl.is_global:
            if flag == 'E':
                bantypes = ''.join(bt for bt in bantypes if bt in Tkl.global_flags()) + ' '
            data = f":{client.id} TKL + {flag} {ident} {host} {set_by} {expire} {set_time} {bantypes}:{reason}"
            IRCD.send_to_servers(client, [], data)

    @staticmethod
    def remove(client, flag, ident, host):
        """
        client:    Source performing the remove.
        """

        if flag not in Tkl.valid_flags():
            return

        for tkl in list(Tkl.table):
            is_match = tkl.type == flag and ((tkl.type == 'Q' and tkl.host == host) or (tkl.ident == ident and tkl.host == host))

            if not is_match:
                continue

            Tkl.table.remove(tkl)

            if client == IRCD.me or client.registered:
                date = datetime.fromtimestamp(float(tkl.set_time)).strftime('%a %b %d %Y %H:%M:%S')
                prefixes = f"{'Expiring ' if tkl.expire else ''}{'Global ' if tkl.is_global else ''}"
                msg = (f"*** {prefixes}{tkl.name} {tkl.mask} removed by {client.fullrealhost} "
                       f"(set by {tkl.set_by} on {date}) [{tkl.reason}]")
                IRCD.log(client, "info", "tkl", "TKL_DEL", msg, sync=not tkl.is_global)

            if tkl.is_global:
                IRCD.send_to_servers(client, [], f":{client.id} TKL - {flag} {tkl.ident} {tkl.host}")

            if tkl.type == 's':
                for shun_client in Tkl.find_matches(tkl):
                    if shun_client.is_shunned():
                        shun_client.flags.remove(Flag.CLIENT_SHUNNED)

    def do_ban(self, client):
        if client.has_flag(Flag.CLIENT_EXIT):
            return
        if client.local:
            client.sendnumeric(Numeric.RPL_TEXT, f"[{self.set_by.split('!')[0]}] {self.reason}")
            IRCD.server_notice(client, f"*** You are banned from this server: {self.reason}")
        client.exit("User has been banned from using this server")

    @staticmethod
    def find_tkl_by_mask(tkltype, mask):
        for tkl in [tkl for tkl in Tkl.table if tkl.type == tkltype]:
            if is_match(tkl.mask.lower(), mask.lower()):
                return tkl

    @staticmethod
    def is_match(client, tkltype):
        """
        Check if 'client' matches any TKL of type 'tkltype'
        If a match is found, the tkl object will be returned.
        Otherwise, None is returned.
        """

        if not client.user or client.has_permission("immune:server-ban"):
            return

        immunity_map = {'k': ("immune:server-ban:kline", "kline"), 'G': ("immune:server-ban:gline", "gline"),
                        'z': ("immune:server-ban:zline:local", "zline"), 'Z': ("immune:server-ban:zline:global", "gzline"),
                        's': ("immune:server-ban:shun", "shun")}

        for tkl in [t for t in Tkl.table if t.type in tkltype]:
            if tkl.type in immunity_map and (
                    client.has_permission(immunity_map[tkl.type][0]) or IRCD.is_except_client(immunity_map[tkl.type][1], client)):
                continue

            if tkl.is_extended():
                if tkl.ident == "~account:":
                    if (tkl.host == '0' and client.user.account == '*') or client.user.account.lower() == tkl.host.lower():
                        return tkl

                elif tkl.ident == "~certfp:" and (fp := client.get_md_value("certfp")):
                    if tkl.host.lower() == fp.lower():
                        return tkl
                    else:
                        if tkl.host == '0':
                            return tkl
                continue

            if tkl.type in "GkZzs":
                ident = '*' if not client.user.username else client.user.username
                test_cases = [f"{ident.lower()}@{client.ip}", f"{ident.lower()}@{client.user.realhost}"]
                for test in test_cases:
                    if is_match(tkl.mask.lower(), test):
                        if tkl.type == 's' and not client.is_shunned():
                            client.add_flag(Flag.CLIENT_SHUNNED)
                        return tkl

            elif tkl.type == 'Q' and is_match(tkl.host.lower(), client.name.lower()):
                return tkl

    @staticmethod
    def find_matches(tkl):
        return [client for client in IRCD.get_clients(local=1, user=1) if Tkl.is_match(client, tkl.type)]

    def __index__(self, num):
        return Tkl.table[num]

    def __repr__(self):
        return f"<TKL '{self.type}' -> '{self.mask} (ident: {self.ident}, host: {self.host})'>"


def remove_expired_tkl():
    current_time = int(time.time())
    for tkl in [t for t in Tkl.table if t.expire]:
        expire_time = int(tkl.expire) + (1 if not tkl.client.local or tkl.client.server and tkl.client != IRCD.me else 0)
        if current_time >= expire_time:
            Tkl.remove(IRCD.me, tkl.type, tkl.ident, tkl.host)


def tkl_to_json():
    result = {}
    for tkl in Tkl.table:
        if tkl.type not in result:
            result[tkl.type] = {}

        result[tkl.type][tkl.mask] = dict(ident=tkl.ident, host=tkl.host, bantypes=tkl.bantypes, reason=tkl.reason, expire=tkl.expire,
                                          set_by=tkl.set_by, set_time=tkl.set_time)

    return result


def tkl_load_from_json(json_data):
    for tkl_type, masks in json_data.items():
        for mask, data in masks.items():
            Tkl.add(client=IRCD.me, flag=tkl_type, ident=data['ident'], host=data['host'], bantypes=data.get('bantypes', '*'),
                    set_by=data['set_by'], expire=data['expire'], set_time=data['set_time'], reason=data['reason'])

    return len(Tkl.table)


def sync_tkl(server):
    for tkl in (tkl for tkl in Tkl.table if tkl.type in Tkl.global_flags()):
        data = f":{IRCD.me.id} TKL + {tkl.type} {tkl.ident} {tkl.host} {tkl.set_by} {tkl.expire} {tkl.set_time} {tkl.bantypes}:{tkl.reason}"
        server.send([], data)


def make_real_mask(data):
    if '@' not in data:
        return f"*@{data}"
    ident, _, host = data.partition('@')
    return f"{ident or '*'}@{host or '*'}"


def cmd_tkl(client, recv):
    if len(recv) < 5 or (recv[1] == '+' and len(recv) < 9):
        return

    flag, ident, host = recv[2], recv[3], recv[4]

    try:
        if recv[1] == '+':
            set_by, expire, set_time = recv[5], int(recv[6]), recv[7]
            if flag == 'E':
                bantypes = recv[8]
                reason = ' '.join(recv[9:]).removeprefix(':').strip()
            else:
                bantypes, reason = '', ' '.join(recv[8:]).removeprefix(':').strip()
            Tkl.add(client, flag, ident, host, bantypes, set_by, expire, set_time, reason)
        elif recv[1] == '-':
            Tkl.remove(client, flag, ident, host)
    except Exception as ex:
        logging.exception(ex)


def cmd_line(client, recv):
    cmd = recv[0].lower()

    if cmd == "sqline":
        reason = ' '.join(recv[2:]).removeprefix(':')
        Tkl.add(client, flag='Q', ident='*', host=recv[1], bantypes='', set_by=client.name, expire=0, set_time=int(time.time()),
                reason=reason)
        return

    elif cmd == "unsqline":
        Tkl.remove(client, 'Q', '*', recv[1])
        return

    if not (cmd_tkl := Tkl.get_flag_of_what(cmd)):
        IRCD.server_notice(client, f"No flag object found for name: {cmd}")
        return

    perm_map = {"kline": "server-ban:kline", "gline": "server-ban:gline", "zline": "server-ban:zline:local",
                "gzline": "server-ban:zline:global", "shun": "server-ban:shun", "eline": "server-ban:eline"}

    if cmd in perm_map and not client.has_permission(perm_map[cmd]):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if len(recv) == 1:
        if stat := Stat.get('G' if cmd_tkl.flag in Tkl.global_flags() else 'g'):
            stat.show(client)
        return

    if recv[1].startswith('-'):
        mask = recv[1].removeprefix('-')
        realmask = make_real_mask(mask)

        if (ident := Tkl.valid_extban(mask)) and len(mask.split(':')) > 1:
            host = mask.split(':')[1]
        else:
            ident, host = realmask.split('@')

        get_mask = Tkl.get_mask(cmd_tkl.flag, ident, host)
        if not Tkl.exists(cmd_tkl.flag, get_mask):
            return IRCD.server_notice(client, f"*** Notice -- No such {cmd_tkl.name}: {get_mask}")
        else:
            Tkl.remove(client, cmd_tkl.flag, ident, host)

    else:
        if len(recv) < 3:
            return client.sendnumeric(Numeric.ERR_NEEDMOREPARAMS, recv[0].upper())

        bantypes = ''
        if cmd_tkl.flag == 'E':
            if len(recv) < 4:
                return client.sendnumeric(Numeric.ERR_NEEDMOREPARAMS, recv[0].upper())

            invalid = ''
            for bantype in recv[2]:
                if bantype not in Tkl.valid_eline_flags() or bantype == cmd_tkl.flag:
                    invalid += bantype
                else:
                    bantypes += bantype

            if invalid:
                return IRCD.server_notice(client, f"Invalid bantypes for {cmd_tkl.name}: {invalid}")

            recv[2:] = recv[3:]

        expire = 0 if recv[2] in ['0', "+0"] else valid_expire(recv[2])
        if recv[2] not in ['0', "+0"] and not expire:
            return IRCD.server_notice(client, f"*** Notice -- Invalid expire: {recv[2]}")

        reason = "No reason specified" if len(recv) < 4 else ' '.join(recv[3:]).strip()
        set_time = int(time.time())
        set_by = client.fullrealhost

        if recv[1].startswith('~') and len(recv[1].split(':')) > 1:
            if not (ident := Tkl.valid_extban(recv[1])):
                return IRCD.server_notice(client, f"Invalid extended server ban: {recv[1].split(':')[0]}")

            host = recv[1].split(':')[1]
            if not host:
                return IRCD.server_notice(client, f"Value missing for extban {ident}")

            if expire:
                expire += set_time

            if ident == "~certfp:" and not re.match(r"[A-Fa-f0-9]{64}$", host):
                return IRCD.server_notice(client, f"Invalid certfp. Must be in format [A-Fa-f0-9]{{64}}")

            if ident == "~account:":
                if host[0].isdigit():
                    return IRCD.server_notice(client, f"Invalid account name: {host} -- cannot start with number")

                if host != '*':
                    invalid = [c for c in host if c.lower() not in IRCD.NICKCHARS]
                    if invalid:
                        return IRCD.server_notice(client, f"Invalid account name: {host} -- invalid characters: {','.join(set(invalid))}")

            Tkl.add(client, flag=cmd_tkl.flag, ident=ident, host=host, bantypes=bantypes, set_by=set_by, expire=expire, set_time=set_time,
                    reason=reason)
            return

        mask = recv[1]
        if cmd_tkl.flag in "Zz":
            ipmask = mask.split('@')[1] if '@' in mask else mask
            ipmask = ipmask.replace('*', '0')
            try:
                ipaddress.ip_address(ipmask)
            except ValueError:
                return IRCD.server_notice(client, f"Invalid IP address for {cmd_tkl.name}: {mask}")

        if '*' not in mask and '@' not in mask and '.' not in mask:
            if not (target := IRCD.find_client(mask, user=1)):
                return client.sendnumeric(Numeric.ERR_NOSUCHNICK, mask)
            ident, host = '*', target.user.realhost
            mask = f"*@{host}"
        else:
            mask = make_real_mask(mask)
            ident, host = mask.split('@')

        if len(mask.replace('*', '')) <= 5 and ('@' in mask or '*' in mask):
            return IRCD.server_notice(client, "*** Notice -- Host range is too small")

        if expire:
            expire += set_time

        if mask:
            set_by = client.fullrealhost
            set_time = int(time.time())
            Tkl.add(client, flag=cmd_tkl.flag, ident=ident, host=host, bantypes=bantypes, set_by=set_by, expire=expire, set_time=set_time,
                    reason=reason)


def cmd_zline(client, recv):
    """
    Bans a user from a server (zline) or entire network (gzline) by IP address.
    -
    Syntax: ZLINE <expire> <nick|ip> <reason>
    Example: ZLINE 1d R00T_UK Be gone.
    This will remove and ban user R00T_UK from the server. Ban will expire in 1 day.
    Banning on nickname only works when the user is currently online.
    -
    Expire formats can be: m (minutes), h (hours), d (days), w (weeks), and M (months, 30 days per unit).
    Stacking (like +1d12h) is not supported.
    -
    To remove a global Z:line, use -ip as the parameter.
    Example: GZLINE -*@12.34.56.78
    """
    cmd_line(client, recv)


def cmd_kline_gline(client, recv):
    """
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
    cmd_line(client, recv)


def cmd_eline(client, recv):
    """
    Exempts a user@host mask from certain ban types on the local server.
    -
    Syntax: ELINE <mask> <bantypes> <expire> <reason>
    Example: ELINE *@somehost.com ZG +1h Temporary exempt from GZ:Line and G:Line.
    -
    Expire formats can be: m (minutes), h (hours), d (days), w (weeks), and M (months, 30 days per unit).
    Stacking (like +1d12h) is not supported.
    -
    To remove an E:Line, use -mask as the parameter first.
    Example: GZLINE -*@somehost.com
    -
    Supported bantypes are:
    k = K:Line
    s = Shun
    z = Z:Line
    F = Spamfilter
    G = G:Line
    Q = Q:Line
    Z = Z:Line
    """
    cmd_line(client, recv)


def cmd_shun(client, recv):
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
    cmd_line(client, recv)


def sqline_check_pre_nick(client, newnick):
    if client.has_permission("immune:server-ban:qline") or not (tkl := Tkl.find_tkl_by_mask('Q', newnick)):
        return Hook.CONTINUE

    client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, newnick, tkl.reason)
    current = f"[Current nick: {client.name}]" if client.name != '*' else ''
    IRCD.send_snomask(client, 'Q', f"*** Q:Line Rejection -- Forbidden nick {newnick} from client {client.ip} {current}")
    return Hook.DENY


def sqline_check_handshake(client):
    if client.has_permission("immune:server-ban:qline") or not (tkl := Tkl.is_match(client, 'Q')):
        return 1

    client.sendnumeric(Numeric.ERR_ERRONEUSNICKNAME, client.name, tkl.reason)
    IRCD.send_snomask(client, 'Q', f"*** Q:Line Rejection -- Forbidden nick {client.name} from client {client.ip}")
    client.name = ''
    return 0


def shun_pre_command(client, recv):
    if not client.user or IRCD.is_except_client("shun", client) or client.has_permission("immune:server-ban:shun"):
        return Hook.CONTINUE

    allowed_commands = {"admin", "part", "quit", "ping", "pong", "motd", "rules"}
    if client.registered and client.is_shunned() and recv[0].lower() not in allowed_commands:
        return Hook.DENY

    return Hook.CONTINUE


def global_tkl_stats(client):
    for t in Tkl.table:
        client.sendnumeric(Numeric.RPL_STATSGLINE, t.type, t.mask, int(t.expire) - int(time.time()) if int(t.expire) else '0', t.set_time,
                           t.set_by, t.reason)


def local_tkl_stats(client):
    for t in [t for t in Tkl.table if t.type not in Tkl.global_flags()]:
        client.sendnumeric(Numeric.RPL_STATSGLINE, t.type, t.mask,
                           int(t.expire) - int(time.time()) if int(t.expire) else '0', t.set_time, t.set_by, t.reason)


def shun_whois(client, whois_client, lines):
    if ((shun_tkl := Tkl.is_match(whois_client, 's')) and whois_client.is_shunned()
            and not whois_client.has_permission("immune:server-ban:shun")):
        line = (Numeric.RPL_WHOISSPECIAL, whois_client.name, "is shunned: " + shun_tkl.reason)
        lines.append(line)


def check_zline(client):
    if client.user and (tkl := Tkl.is_match(client, "Zz")):
        tkl.do_ban(client)


def check_bans(client, *args):
    if client.user and (tkl := Tkl.is_match(client, "Gk")):
        tkl.do_ban(client)
        return Hook.DENY
    return Hook.CONTINUE


def init(module):
    Command.add(module, cmd_tkl, "TKL", 3, Flag.CMD_SERVER)
    Command.add(module, cmd_kline_gline, "KLINE", 0, Flag.CMD_OPER)
    Command.add(module, cmd_kline_gline, "GLINE", 0, Flag.CMD_OPER)
    Command.add(module, cmd_zline, "ZLINE", 0, Flag.CMD_OPER)
    Command.add(module, cmd_zline, "GZLINE", 0, Flag.CMD_OPER)
    Command.add(module, cmd_shun, "SHUN", 0, Flag.CMD_OPER)
    Command.add(module, cmd_line, "SQLINE", 1, Flag.CMD_SERVER)
    Command.add(module, cmd_line, "UNSQLINE", 1, Flag.CMD_SERVER)
    Command.add(module, cmd_eline, "ELINE", 0, Flag.CMD_OPER)
    Hook.add(Hook.NEW_CONNECTION, check_zline, priority=999)
    Hook.add(Hook.PRE_CONNECT, check_bans)
    Hook.add(Hook.IS_HANDSHAKE_FINISHED, sqline_check_handshake)
    Hook.add(Hook.PRE_COMMAND, shun_pre_command)
    Hook.add(Hook.PRE_LOCAL_NICKCHANGE, sqline_check_pre_nick)
    Hook.add(Hook.LOOP, remove_expired_tkl)
    Hook.add(Hook.ACCOUNT_LOGIN, check_bans)
    Hook.add(Hook.SERVER_SYNC, sync_tkl)
    Hook.add(Hook.WHOIS, shun_whois)
    Stat.add(module, global_tkl_stats, 'G', "View all active TKLs")
    Stat.add(module, local_tkl_stats, 'g', "View only local active TKLs")
    Tkl.add_flag(flag='k', name="K:Line", what="kline", host_format=1, is_global=0, allow_eline=1)
    Tkl.add_flag(flag='s', name="Shun", what="shun", host_format=1, is_global=0, allow_eline=1)
    Tkl.add_flag(flag='z', name="Z:Line", what="zline", host_format=0, is_global=0, allow_eline=1)
    Tkl.add_flag(flag='E', name="E:Line", what="eline", host_format=1, is_global=0)
    Tkl.add_flag(flag='F', name="Spamfilter", what="spamfilter", host_format=1, is_global=0, allow_eline=1)
    Tkl.add_flag(flag='G', name="G:Line", what="gline", host_format=1, is_global=1, allow_eline=1)
    Tkl.add_flag(flag='Q', name="Q:Line", what="qline", host_format=0, is_global=1, allow_eline=1)
    Tkl.add_flag(flag='Z', name="Z:Line", what="gzline", host_format=1, is_global=1, allow_eline=1)
