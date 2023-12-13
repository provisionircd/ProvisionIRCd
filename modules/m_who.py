"""
/who command
"""

from handle.core import IRCD, Command, Isupport, Numeric
from handle.functions import is_match


def get_who_status(client, user_client, channel=None):
    who_status = ''
    who_status += 'G' if user_client.user.away else 'H'
    if 'r' in user_client.user.modes:
        who_status += 'r'
    if 'B' in user_client.user.modes:
        who_status += 'B'
    if 'z' in user_client.user.modes:
        who_status += 's'
    if 'o' in user_client.user.modes:
        who_status += '*'
    if channel:
        status = ''
        for cmode in [cmode for cmode in channel.get_membermodes_sorted() if channel.client_has_membermodes(user_client, cmode.flag)]:
            status += cmode.prefix
        who_status += status
    if 'H' in user_client.user.modes and 'o' in client.user.modes:
        who_status += '!'

    return who_status


class WhoData:
    replies = []

    def __init__(self, who_client):
        self.who_client = who_client
        self.username = ''
        self.cloakhost = ''
        self.server_name = ''
        self.name = ''
        self.status = ''
        self.hopcount = 0
        self.user_info = ''
        self.fields = []
        self.channel = None
        if who_client.channels:
            self.channel = who_client.channels[0]
        self.flags = ''
        self.fields = ['', '', '', '', '', '', '', '', '', '', '', '', '']
        if self not in WhoData.replies:
            WhoData.replies.append(self)

    def make(self, client):
        self.username = self.who_client.user.username
        self.cloakhost = self.who_client.user.cloakhost
        # self.server_name = self.who_client.user.server.name
        self.server_name = self.who_client.uplink.name
        self.name = self.who_client.name
        self.hopcount = self.who_client.hopcount
        self.user_info = self.who_client.info
        self.status = get_who_status(client, self.who_client, self.channel)
        if self.channel and not self.channel.user_can_see_member(client, self.who_client):
            self.channel = None
            for chan in self.who_client.channels:
                if chan.user_can_see_member(client, self.who_client):
                    self.channel = chan
                    break

    def who_reply(self):
        # Invalid: *  9b798cb3.20126204.b5c219d3.IP dev.provisionweb.org * H :0
        # mask, user_client.user.username, user_client.user.cloakhost, client.user.server.name, user_client.name, status, user_client.hopcount, user_client.info
        return '*' if not self.channel else self.channel.name, self.username, self.cloakhost, self.server_name, self.name, self.status, self.hopcount, self.user_info


def get_who_reply(who_client):
    for reply in WhoData.replies:
        if reply.who_client == who_client:
            return reply
    return WhoData(who_client)


def send_who_reply(client, mask: str):
    for reply in WhoData.replies:
        if 'i' in reply.who_client.user.modes:
            if 'o' not in client.user.modes and not IRCD.common_channels(client, reply.who_client) and reply.who_client != client:
                continue
        if reply.fields != [''] * 13:
            # reply_string = mask + ' ' + ' '.join(reply.fields)
            reply_string = mask + ' ' + ' '.join(map(str, reply.fields))
            client.sendnumeric(Numeric.RPL_WHOSPCRPL, reply_string)
        else:
            if 'I' in reply.flags and 'o' in client.user.modes:
                reply.cloakhost = reply.who_client.ip

            elif 'R' in reply.flags and 'o' in client.user.modes:
                reply.cloakhost = reply.who_client.user.realhost

            if reply.channel:
                if not reply.channel.user_can_see_member(client, reply.who_client):
                    reply.channel = None
                    for chan in reply.who_client.channels:
                        if chan.user_can_see_member(client, reply.who_client):
                            reply.channel = chan
                            break

            client.sendnumeric(Numeric.RPL_WHOREPLY, *reply.who_reply())

    client.sendnumeric(Numeric.RPL_ENDOFWHO, mask)


def cmd_who(client, recv):
    """
    View information about users on the server.
    -
    Syntax: WHO <target> [flags]
    -
    Wildcards are accepted in <target>, so * matches all channels on the network.
    Flags are optional, and can be used to filter the output.
    They work similar to modes, + for positive and - for negative.
    -
     a <name>       = Match on account name.
     n <nickname>   = Match on nickname.
     h <host>       = User has <host> in the hostname.
     o              = Show only IRC operators.
     r <realname>   = Filter by realname.
     s <server      = Filter by server.
     u <ident>      = Filter by username/ident.
    """

    WhoData.replies = []

    if len(recv) == 1 or recv[1] == '*':
        who_mask = '*'  # Match all.
    else:
        who_mask = recv[1]

    token = ''
    flags = ''
    whox = 0
    if len(recv) > 2:
        flags = recv[2]
        if flags.startswith('%'):
            if len(flags.split(',')) > 1:
                token = flags.split(',')[1]

    for mask in who_mask.split(','):
        who_matches = []
        if who_channel := IRCD.find_channel(mask):
            who_matches = who_channel.clients()
        elif (user := IRCD.find_user(mask)) and user.registered:
            who_matches.append(user)
        else:
            who_matches = [c for c in IRCD.global_registered_users() if is_match(mask, c.ip)]

        for char in flags:
            if char == '%':
                whox = 1
            if not whox:
                if char == 'n':
                    who_matches = []
                    for find_client in [c for c in IRCD.global_registered_clients() if is_match(mask.lower(), c.name.lower())]:
                        if find_client not in who_matches:
                            who_matches.append(find_client)

                if char == 'u':
                    who_matches = []
                    for find_client in [c for c in IRCD.global_registered_clients() if is_match(mask.lower(), c.user.username.lower())]:
                        if find_client not in who_matches:
                            who_matches.append(find_client)

                if char == 'h':
                    who_matches = []
                    if 'o' not in client.user.modes:
                        continue
                    for find_client in [c for c in IRCD.global_registered_clients() if is_match(mask.lower(), c.user.realhost.lower())]:
                        if find_client not in who_matches:
                            who_matches.append(find_client)

                if char == 'i':
                    who_matches = []
                    if 'o' not in client.user.modes:
                        continue
                    for find_client in [c for c in IRCD.global_registered_clients() if is_match(mask, c.ip)]:
                        if find_client not in who_matches:
                            who_matches.append(find_client)

                if char == 's':
                    who_matches = []
                    if 'o' not in client.user.modes:
                        continue
                    for find_client in [c for c in IRCD.global_registered_clients() if is_match(mask.lower(), c.uplink.name.lower())]:
                        if find_client not in who_matches:
                            who_matches.append(find_client)

                if char == 'r':
                    who_matches = []
                    for find_client in [c for c in IRCD.global_registered_clients() if is_match(mask.lower(), c.info.lower())]:
                        if find_client not in who_matches:
                            who_matches.append(find_client)

                if char == 'a':
                    who_matches = []
                    for find_client in [c for c in IRCD.global_registered_clients() if is_match(mask.lower(), c.user.account.lower())]:
                        if find_client not in who_matches:
                            who_matches.append(find_client)

                if char == 'm':
                    who_matches = []
                    if 'o' not in client.user.modes:
                        continue
                    if mask.startswith('-'):
                        condition = '-'
                        mode_mask = mask[1:]
                    else:
                        mode_mask = mask
                        condition = '+'
                    for mode in mode_mask:
                        for find_client in IRCD.global_registered_users():
                            if condition == '+' and mode not in find_client.user.modes:
                                continue
                            if condition == '-' and mode in find_client.user.modes:
                                continue
                            if find_client not in who_matches:
                                who_matches.append(find_client)

                if char == 'd':
                    who_matches = []
                    if not mask.isdigit():
                        continue
                    for find_client in [c for c in IRCD.global_registered_clients() if c.hopcount == int(mask)]:
                        if find_client not in who_matches:
                            who_matches.append(find_client)

            else:
                for who_client in who_matches:
                    who_reply = get_who_reply(who_client)
                    if char == 't' and token:
                        who_reply.fields[0] = token

                    if char == 'c':
                        if who_client.channels:
                            chan = who_client.channels[0].name
                        else:
                            chan = '*'
                        who_reply.fields[1] = chan

                    if char == 'u':
                        who_reply.fields[2] = who_client.user.username

                    if char == 'i':
                        if 'o' in client.user.modes:
                            ip = who_client.ip
                        else:
                            ip = "255.255.255.255"
                        who_reply.fields[3] = ip

                    if char == 'h':
                        who_reply.fields[4] = who_client.user.realhost

                    if char == 's':
                        # who_reply.fields[5] = who_client.user.server.name
                        who_reply.fields[5] = who_client.uplink.name

                    if char == 'n':
                        who_reply.fields[6] = who_client.name

                    if char == 'f':
                        who_channel = next((c for c in IRCD.get_channels() if IRCD.common_channels(who_client, client)), 0)
                        who_status = get_who_status(client, who_client, who_channel)
                        who_reply.fields[7] = who_status

                    if char == 'd':
                        who_reply.fields[8] = str(who_client.hopcount)

                    if char == 'l':
                        who_reply.fields[9] = str(who_client.idle_since)

                    if char == 'a':
                        if (account := who_client.user.account) != '*':
                            who_reply.fields[10] = account
                        else:
                            who_reply.fields[10] = '0'

                    if char == 'o':
                        status = ''
                        if who_channel := IRCD.find_channel(mask):
                            for cmode in [cmode for cmode in who_channel.get_membermodes_sorted() if who_channel.client_has_membermodes(who_client, cmode.flag)]:
                                status += cmode.prefix
                        who_reply.fields[11] = status
                    if 'r' in flags:
                        who_reply.fields[12] = who_client.info

        for who_client in who_matches:
            who_reply = get_who_reply(who_client)
            who_reply.flags = flags
            who_reply.make(client)

        send_who_reply(client, mask)


def init(module):
    Isupport.add("WHOX")
    Command.add(module, cmd_who, "WHO")
