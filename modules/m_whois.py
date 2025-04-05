"""
/whois and /whowas command
"""

import datetime
import time

from handle.core import IRCD, Command, Usermode, Flag, Numeric, Hook
from handle.logger import logging


class WhowasData:
    entries = []

    def __init__(self, nickname, ident, cloakhost, vhost, realhost, ip, realname, signon, signoff, server, account, certfp):
        self.nickname = nickname
        self.ident = ident
        self.cloakhost = cloakhost
        self.vhost = vhost
        self.realhost = realhost
        self.ip = ip
        self.realname = realname
        self.signon = signon
        self.signoff = signoff
        self.server = server
        self.account = account
        self.certfp = certfp
        WhowasData.entries.append(self)
        WhowasData.remove_old(nickname)

    @staticmethod
    def remove_old(nickname):
        nick_entries = [e for e in WhowasData.entries if e.nickname.lower() == nickname.lower()]
        while len(nick_entries) > 12:
            oldest = sorted(nick_entries, key=lambda e: e.signoff)[0]
            WhowasData.entries.remove(oldest)
            nick_entries.remove(oldest)

    @staticmethod
    def count(nickname):
        return len([e for e in WhowasData.entries if e.nickname.lower() == nickname.lower()])

    @staticmethod
    def get_nick_entries(nickname):
        return [e for e in WhowasData.entries if e.nickname.lower() == nickname.lower()]

    def get_date_string(self):
        dt = datetime.datetime.fromtimestamp(self.signoff)
        return f"{dt.strftime('%a %b %d')} {dt.strftime('%H:%M:%S %Z').strip()} {dt.strftime('%Y')}"


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
        client.sendnumeric(Numeric.RPL_WHOWASUSER, entry.nickname, entry.ident, entry.vhost, entry.realname)
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
               vhost=client.user.vhost,
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

    if not (target := IRCD.find_client(recv[1], user=1)):
        client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])
        client.sendnumeric(Numeric.RPL_ENDOFWHOIS, recv[1])
        return

    user = target.user
    is_self = (target == client)
    is_oper = ('o' in client.user.modes)
    client.add_flood_penalty(1000)

    if 'W' in user.modes and not is_self:
        msg = f"*** Notice -- {client.name} ({client.user.username}@{client.user.realhost}) did a /WHOIS on you."
        if target.local:
            IRCD.server_notice(target, msg)
        else:
            IRCD.send_to_one_server(target.uplink, [], f":{IRCD.me.name} NOTICE {target.id} :{msg}")

    client.sendnumeric(Numeric.RPL_WHOISUSER, target.name, user.username, user.host, target.info)

    if is_oper or is_self:
        snomask_str = " +" + user.snomask if user.snomask else ''
        client.sendnumeric(Numeric.RPL_WHOISMODES, target.name, user.modes, snomask_str)

    if (is_oper or is_self) and not client.is_uline() and 'S' not in user.modes:
        client.sendnumeric(Numeric.RPL_WHOISHOST, target.name, '*', user.realhost, target.ip)

    if 'r' in user.modes and user.account != '*':
        client.sendnumeric(Numeric.RPL_WHOISREGNICK, target.name)

    if 'S' not in user.modes and not target.is_uline():
        if 'c' not in user.modes or is_oper or is_self:
            channels = []
            for channel in target.channels():
                visible = 1
                if not channel.user_can_see_member(client, target):
                    if client.has_permission("channel:see:whois"):
                        visible = 2
                    else:
                        continue

                prefix = ''
                if visible == 2:
                    prefix += '?'
                if (('s' in channel.modes or 'p' in channel.modes) and not is_self
                        and not channel.find_member(client) and not client.has_permission("channel:see:whois")):
                    continue
                if ('s' in channel.modes or 'p' in channel.modes) and '!' not in prefix and '?' not in prefix:
                    prefix += '?'
                if 'c' in user.modes and (is_oper or is_self) and '?' not in prefix:
                    prefix += '!'
                prefix += channel.get_membermodes_sorted(client=target, prefix=1)
                channels.append(f"{prefix}{channel.name}")

            if channels:
                client.sendnumeric(Numeric.RPL_WHOISCHANNELS, target.name, ' '.join(channels))

    client.sendnumeric(Numeric.RPL_WHOISSERVER, target.name, target.uplink.name, target.uplink.info)

    if user.away:
        client.sendnumeric(Numeric.RPL_AWAY, target.name, user.away)

    if 'H' not in user.modes or is_oper:
        if 'o' in user.modes and 'S' not in user.modes:
            extra_info = ''
            show_acc = (target.user.operclass and client.user.operclass) or is_self
            if show_acc and target.user.operclass and is_oper:
                extra_info = f" [{target.user.operclass.name}]"
            client.sendnumeric(Numeric.RPL_WHOISOPERATOR, target.name, "an IRC Operator", extra_info)

    if 'z' in user.modes and 'S' not in user.modes and not target.is_uline():
        client.sendnumeric(Numeric.RPL_WHOISSECURE, target.name)

    if target.local and target.local.flood_penalty > 10_000 and is_oper:
        client.sendnumeric(Numeric.RPL_WHOISSPECIAL, target.name, f"has flood penalty: {target.local.flood_penalty}")

    for swhois in user.swhois:
        if swhois.tag == "oper" and 'H' in user.modes and not is_oper:
            continue
        client.sendnumeric(Numeric.RPL_WHOISSPECIAL, target.name, swhois.line)

    lines = []
    IRCD.run_hook(Hook.WHOIS, client, target, lines)
    for line in lines:
        client.sendnumeric(*line)

    # Idle time.
    can_see_hidden_idle = client.has_permission("immune:whois:hideidle")
    if 'S' not in user.modes and not target.is_uline() and ('I' not in user.modes or can_see_hidden_idle or is_self):
        client.sendnumeric(Numeric.RPL_WHOISIDLE, target.name, int(time.time()) - target.idle_since, target.creationtime)

    # Service flag.
    if 'S' in user.modes:
        client.sendnumeric(Numeric.RPL_WHOISOPERATOR, target.name, "a Network Service", '')

    client.sendnumeric(Numeric.RPL_ENDOFWHOIS, target.name)


def remove_expired_whowas():
    current_time = int(time.time())
    WhowasData.entries = [entry for entry in WhowasData.entries if current_time - entry.signoff <= 3600 * 24 * 30]


def init(module):
    Command.add(module, cmd_whois, "WHOIS", 0, Flag.CMD_USER)
    Command.add(module, cmd_whowas, "WHOWAS", 0, Flag.CMD_USER)
    Usermode.add(module, 'c', 1, 0, Usermode.allow_all, "Hide channels in /WHOIS")
    Usermode.add(module, 'I', 1, 0, Usermode.allow_all, "Hide idle time in /WHOIS")
    Usermode.add(module, 'W', 1, 1, Usermode.allow_opers, "See when people are doing a /WHOIS on you")
    for hook in [Hook.LOCAL_QUIT, Hook.REMOTE_QUIT, Hook.LOCAL_NICKCHANGE, Hook.REMOTE_NICKCHANGE]:
        Hook.add(hook, savewhowas)
    Hook.add(Hook.LOOP, remove_expired_whowas)
