"""
/whois and /whowas command
"""

import datetime
import time

from handle.core import Flag, Numeric, Command, Usermode, IRCD, Hook


class WhowasData:
    entries = []

    def __init__(self, nickname, ident, cloakhost, realhost, ip, realname, signon, signoff, server, account, certfp):
        self.nickname = nickname
        self.ident = ident
        self.cloakhost = cloakhost
        self.realhost = realhost
        self.ip = ip
        self.realname = realname
        self.signon = signon
        self.signoff = signoff
        self.server = server
        self.account = account
        self.certfp = certfp
        WhowasData.entries.append(self)
        WhowasData.remove_old(self.nickname)

    @staticmethod
    def remove_old(nickname):
        while WhowasData.count(nickname) > 12:
            last = sorted([e for e in WhowasData.get_nick_entries(nickname)], key=lambda e: e.signoff)[0]
            WhowasData.entries.remove(last)

    @staticmethod
    def count(nickname):
        return len([e for e in WhowasData.entries if e.nickname.lower() == nickname.lower()])

    @staticmethod
    def get_nick_entries(nickname):
        return [e for e in WhowasData.entries if e.nickname.lower() == nickname.lower()]

    def get_date_string(self):
        d = datetime.datetime.fromtimestamp(self.signoff).strftime('%a %b %d')
        t = datetime.datetime.fromtimestamp(self.signoff).strftime('%H:%M:%S %Z').strip()
        y = datetime.datetime.fromtimestamp(self.signoff).strftime('%Y')
        return f"{d} {t} {y}"


def cmd_whowas(client, recv):
    """
    Syntax: WHOWAS <nickname>
    -
    Request saved user information for offline users.
    This information also includes account and certfp.
    """

    if len(recv) < 2:
        return client.sendnumeric(Numeric.ERR_NONICKNAMEGIVEN)
    if not (entries := WhowasData.get_nick_entries(recv[1])):
        client.sendnumeric(Numeric.ERR_WASNOSUCHNICK, recv[1])
        client.sendnumeric(Numeric.RPL_ENDOFWHOWAS, recv[1])
        return

    for entry in entries:
        client.sendnumeric(Numeric.RPL_WHOWASUSER, entry.nickname, entry.ident, entry.cloakhost, entry.realname)
        if 'o' in client.user.modes:
            client.sendnumeric(Numeric.RPL_WHOISHOST, entry.nickname, '*', entry.realhost, entry.ip)
        client.sendnumeric(Numeric.RPL_WHOISSERVER, entry.nickname, entry.server, entry.get_date_string())
        if entry.account != '*':
            client.sendnumeric(Numeric.RPL_WHOISACCOUNT, entry.nickname, entry.account)
        if entry.certfp:
            client.sendnumeric(Numeric.RPL_WHOISCERTFP, entry.nickname, entry.certfp)
    client.sendnumeric(Numeric.RPL_ENDOFWHOWAS, recv[1])


def savewhowas(client, *args):
    if not client.user:
        return
    certfp = client.get_md_value("certfp")
    WhowasData(nickname=client.name,
               ident=client.user.username,
               cloakhost=client.user.cloakhost,
               realhost=client.user.realhost,
               ip=client.ip,
               realname=client.info,
               signon=client.creationtime,
               signoff=int(time.time()),
               server=client.uplink.name,
               account=client.user.account,
               certfp=certfp)


def cmd_whois(client, recv):
    """
    Displays information about the given user, such as hostmask, channels, idle time, etc...
    Output may vary depending on user- and channel modes.
    -
    Example: WHOIS Alice
    """

    if len(recv) < 2:
        client.sendnumeric(Numeric.ERR_NONICKNAMEGIVEN)
        return
    if not (target := IRCD.find_user(recv[1])):
        client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])
        client.sendnumeric(Numeric.RPL_ENDOFWHOIS, recv[1])
        return

    if 'W' in target.user.modes and target != client:
        msg = f'*** Notice -- {client.name} ({client.user.username}@{client.user.realhost}) did a /WHOIS on you.'
        if target.local:
            IRCD.server_notice(target, msg)
        else:
            data = f':{IRCD.me.name} NOTICE {target.id} :{msg}'
            IRCD.send_to_one_server(target.uplink, [], data)

    lines = []

    user = target.user

    client.sendnumeric(Numeric.RPL_WHOISUSER, target.name, target.user.username, target.user.cloakhost, target.info)

    if 'o' in client.user.modes or target == client:
        client.sendnumeric(Numeric.RPL_WHOISMODES, target.name, target.user.modes, " +" + target.user.snomask if target.user.snomask else "")

    if ('o' in client.user.modes or target == client) and not client.ulined and 'S' not in target.user.modes:
        client.sendnumeric(Numeric.RPL_WHOISHOST, target.name, '*', target.user.realhost, target.ip)

    if 'r' in target.user.modes and user.account != '*':
        client.sendnumeric(Numeric.RPL_WHOISREGNICK, target.name)

    if 'S' not in target.user.modes and not target.ulined:
        if 'c' not in target.user.modes or ('o' in client.user.modes or target == client):
            channels = []
            for channel in target.user.channels:
                visible = 1
                if not channel.user_can_see_member(client, user):
                    if client.has_permission("channel:see:whois"):
                        visible = 2
                    else:
                        break

                prefix = ''
                if visible == 2:
                    prefix += '?'
                if 's' in channel.modes or 'p' in channel.modes:
                    if target != client and not channel.find_member(client) and not client.has_permission("channel:see:whois"):
                        continue
                    if '!' not in prefix and '?' not in prefix:
                        prefix += '?'
                if 'c' in user.modes and ('o' in client.user.modes or target == client) and '?' not in prefix:
                    prefix += '!'
                prefix += channel.get_prefix_sorted_str(target)
                channels.append(f'{prefix}{channel.name}')
            if channels:
                client.sendnumeric(Numeric.RPL_WHOISCHANNELS, target.name, ' '.join(channels))

    client.sendnumeric(Numeric.RPL_WHOISSERVER, target.name, target.uplink.name, target.uplink.info)

    if target.user.away:
        client.sendnumeric(Numeric.RPL_AWAY, target.name, target.user.away)

    if 'H' not in target.user.modes or 'o' in client.user.modes:
        if 'o' in target.user.modes and 'S' not in target.user.modes:
            extra_info = ""
            show_acc = 1 if (target.user.operclass and client.user.operclass) or target == client else 0
            if show_acc and target.user.operclass:
                extra_info = "" if "o" not in client.user.modes or not show_acc else f" [{target.user.operclass.name}]"
            client.sendnumeric(Numeric.RPL_WHOISOPERATOR, target.name, "an IRC Operator", extra_info)

    if 'z' in target.user.modes and 'S' not in target.user.modes and not target.ulined:
        client.sendnumeric(Numeric.RPL_WHOISSECURE, target.name)

    if target.local and target.local.flood_penalty > 10_000 and 'o' in client.user.modes:
        client.sendnumeric(Numeric.RPL_WHOISSPECIAL, target.name, f"has flood penalty: {target.local.flood_penalty}")

    for swhois in target.user.swhois:
        if swhois.remove_on_deoper:
            if 'H' in target.user.modes and 'o' not in client.user.modes:
                continue

        client.sendnumeric(Numeric.RPL_WHOISSPECIAL, target.name, swhois.line)

    IRCD.run_hook(Hook.WHOIS, client, target, lines)

    for line in lines:
        client.sendnumeric(*line)

    if 'S' not in target.user.modes and not target.ulined:
        client.sendnumeric(Numeric.RPL_WHOISIDLE, target.name, int(time.time()) - target.idle_since, target.creationtime)

    if 'S' in target.user.modes:
        client.sendnumeric(Numeric.RPL_WHOISOPERATOR, target.name, "a Network Service", '')

    client.sendnumeric(Numeric.RPL_ENDOFWHOIS, target.name)


def remove_expired_whowas():
    for entry in list(WhowasData.entries):
        if int(time.time()) - entry.signoff > 3600 * 24 * 30:  # 1 month expire?
            WhowasData.entries.remove(entry)


def init(module):
    Command.add(module, cmd_whois, "WHOIS", 0, Flag.CMD_USER)
    Command.add(module, cmd_whowas, "WHOWAS", 0, Flag.CMD_USER)
    Usermode.add(module, 'c', 1, 0, Usermode.allow_all, "Hide channels in /WHOIS")
    Usermode.add(module, 'W', 1, 1, Usermode.allow_opers, "See when people are doing a /WHOIS on you")
    Hook.add(Hook.LOCAL_QUIT, savewhowas)
    Hook.add(Hook.REMOTE_QUIT, savewhowas)
    Hook.add(Hook.LOCAL_NICKCHANGE, savewhowas)
    Hook.add(Hook.REMOTE_NICKCHANGE, savewhowas)
    Hook.add(Hook.LOOP, remove_expired_whowas)
