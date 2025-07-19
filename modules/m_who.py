"""
/who command
"""

from time import time

from handle.core import IRCD, Command, Isupport, Numeric, Hook
from handle.functions import is_match


def get_who_status(client, target_client, channel=None):
    status = 'G' if target_client.user.away else 'H'

    if 'r' in target_client.user.modes:
        status += 'r'
    if 'z' in target_client.user.modes:
        status += 's'
    if 'o' in target_client.user.modes:
        status += '*'
    if channel:
        prefixes = (m.prefix for m in channel.get_membermodes_sorted() if channel.client_has_membermodes(target_client, m.flag))
        status += ''.join(prefixes)

    if 'H' in target_client.user.modes and 'o' in client.user.modes:
        status += '!'

    for result, cb in Hook.call(Hook.WHO_STATUS, args=(client, target_client)):
        if result and isinstance(result, str) and len(result) == 1 and result not in status:
            status += result

    return status


class WhoData:

    def __init__(self, who_client):
        self.who_client = who_client
        self.username = who_client.user.username
        self.vhost = who_client.user.vhost
        self.server_name = who_client.uplink.name
        self.name = who_client.name
        self.hopcount = who_client.hopcount
        self.user_info = who_client.info
        self.status = ''
        self.channel = next((c for c in who_client.channels()), None)
        self.flags = ''
        self.fields = [''] * 13

    def make(self, client):
        self.status = get_who_status(client, self.who_client, self.channel)

        if self.channel and not self.channel.user_can_see_member(client, self.who_client):
            for chan in self.who_client.channels():
                if chan.user_can_see_member(client, self.who_client):
                    self.channel = chan
                    break
            else:
                self.channel = None

    def who_reply(self):
        channel_name = '*' if not self.channel else self.channel.name
        return channel_name, self.username, self.vhost, self.server_name, self.name, self.status, self.hopcount, self.user_info


def who_can_see_channel(client, channel, who_target):
    if not channel.user_can_see_member(client, who_target):
        return 0

    if 's' in channel.modes and not channel.find_member(client) and not client.has_permission("channel:see:who:secret"):
        return 0

    if 'i' in who_target.user.modes and not channel.find_member(client) and not client.has_permission("channel:see:who:invisible"):
        return 0

    return 1


def send_who_reply(client, who_data_list, mask, whox):
    for data in who_data_list:
        if whox:
            reply_string = ' '.join(str(field) for field in data.fields if field)
            client.sendnumeric(Numeric.RPL_WHOSPCRPL, reply_string)
        else:
            if 'I' in data.flags and 'o' in client.user.modes:
                data.vhost = data.who_client.ip
            elif 'R' in data.flags and 'o' in client.user.modes:
                data.vhost = data.who_client.user.realhost

            if data.channel:
                for channel in data.who_client.channels():
                    if who_can_see_channel(client, channel, data.who_client):
                        data.channel = channel
                        break
                else:
                    data.channel = None

            client.add_flood_penalty(100)
            client.sendnumeric(Numeric.RPL_WHOREPLY, *data.who_reply())

    client.sendnumeric(Numeric.RPL_ENDOFWHO, mask)


def filter_clients(clients, flag, flag_match, flag_true, client=None):
    initial_clients = list(clients)
    filtered_matches = initial_clients

    if flag == 'n':
        filtered_matches = (c for c in initial_clients if is_match(flag_match.lower(), c.name.lower()))
    elif flag == 'u':
        filtered_matches = (c for c in initial_clients if is_match(flag_match.lower(), c.user.username.lower()))
    elif flag == 'h' and client and 'o' in client.user.modes:
        filtered_matches = (c for c in initial_clients if is_match(flag_match.lower(), c.user.realhost.lower()))
    elif flag == 'i' and client and 'o' in client.user.modes:
        filtered_matches = (c for c in initial_clients if is_match(flag_match, c.ip))
    elif flag == 's' and client and 'o' in client.user.modes:
        filtered_matches = (c for c in initial_clients if is_match(flag_match.lower(), c.uplink.name.lower()))
    elif flag == 'r':
        filtered_matches = (c for c in initial_clients if is_match(flag_match.lower(), c.info.lower()))
    elif flag == 'a':
        filtered_matches = (c for c in initial_clients if is_match(flag_match.lower(), c.user.account.lower()))
    elif flag == 'o':
        filtered_matches = (c for c in initial_clients if 'o' in c.user.modes)
    else:
        return initial_clients

    if flag_true:
        final_list = list(filtered_matches)
        return final_list
    else:
        matches_to_exclude = set(filtered_matches)
        final_list = [c for c in initial_clients if c not in matches_to_exclude]
        return final_list


def process_whox_field(data, flag, token, mask, client):
    """ Process a single WHOX field for a client. """
    who_client = data.who_client
    current_time = int(time())

    if flag == 't' and token:
        data.fields[0] = token
    elif flag == 'c':
        data.fields[1] = who_client.channels()[0].name if who_client.channels() else '*'
    elif flag == 'u':
        data.fields[2] = who_client.user.username
    elif flag == 'i':
        data.fields[3] = who_client.ip if 'o' in client.user.modes else "255.255.255.255"
    elif flag == 'h':
        data.fields[4] = who_client.user.vhost
    elif flag == 's':
        data.fields[5] = who_client.uplink.name
    elif flag == 'n':
        data.fields[6] = who_client.name
    elif flag == 'f':
        common_channel = next((c for c in IRCD.get_channels() if IRCD.common_channels(who_client, client)), None)
        data.fields[7] = get_who_status(client, who_client, common_channel)
    elif flag == 'd':
        data.fields[8] = str(who_client.hopcount)
    elif flag == 'l':
        data.fields[9] = str(current_time - who_client.idle_since)
    elif flag == 'a':
        account = who_client.user.account
        data.fields[10] = account if account != '*' else '0'

    elif flag == 'o':
        channel_context = (IRCD.find_channel(mask) or next((c for c in who_client.channels() if c.find_member(client)), None))
        if not channel_context and 'o' in client.user.modes and who_client.channels():
            channel_context = who_client.channels()[0]
        if channel_context:
            status = ''.join(m.prefix for m in channel_context.get_membermodes_sorted() if channel_context.client_has_membermodes(who_client, m.flag))
            data.fields[11] = status
        else:
            data.fields[11] = ''

    elif flag == 'r':
        data.fields[12] = ':' + who_client.info


def matches_who_mask(client, mask, c):
    lowered_mask = mask.lower()
    fields_to_check = [c.name.lower(), c.user.vhost.lower()]
    if 'o' in client.user.modes:
        fields_to_check.extend([c.ip, c.user.realhost.lower()])
    return any(is_match(lowered_mask, field) for field in fields_to_check)


def is_client_visible(client, c):
    return 'i' not in c.user.modes or IRCD.common_channels(client, c) or client.has_permission("channel:see:who:invisible") or c == client


def find_matching_clients(client, mask):
    if chan := IRCD.find_channel(mask):
        if 's' in chan.modes and not chan.find_member(client) and not client.has_permission("channel:see:who:secret"):
            return []

        return (c for c in chan.clients() if chan.user_can_see_member(client, c)
                and ('i' not in c.user.modes or chan.find_member(client) or client.has_permission("channel:see:who:invisible")))

    if (user := IRCD.find_client(mask)) and user.registered:
        return [user]

    return (c for c in IRCD.get_clients(user=1, registered=1) if is_client_visible(client, c) and matches_who_mask(client, mask, c))


def cmd_who(client, recv):
    """
    View information about users on the server.
    -
    Syntax: WHO <target[,target2,...]> [flags] [params...]
    Syntax: WHO <target[,target2,...]> [%<fields>[,<token>]]
    -
    The WHO command can be used to get information about users on the network.
    Multiple targets can be specified in a comma-separated list.
    Wildcards (*, ?) are accepted in the target mask.
    -
    The command has two modes of operation: Legacy and WHOX.
    ---------------------------------------------------------------------
    Legacy Filtering Flags (+/-)
    ---------------------------------------------------------------------
    Legacy mode uses flags to filter the result list. Flags can be prefixed
    with '+' to include matches or '-' to exclude them. A parameter with
    spaces must be the final argument.
    -
     o              = Filter for global IRC Operators.
     n <nickname>   = Filter by nickname.
     u <ident>      = Filter by username/ident.
     h <host>       = Filter by hostname (operator only).
     r <realname>   = Filter by real name.
     s <server>     = Filter by server name (operator only).
    ---------------------------------------------------------------------
    WHOX Extension (%fields)
    ---------------------------------------------------------------------
    WHOX mode is triggered by using the '%' character. It allows for a
    completely customized reply containing only the fields you request.
    An optional numeric token (max 3 digits) can be provided for tracking.
    -
     %<fields>[,<token>]
    -
    WHOX Fields:
     t = The client-specified <token>.
     c = A channel the user is in.
     u = Username (ident).
     i = IP address.
     h = Hostname.
     s = Server name.
     n = Nickname.
     f = Flags (H/G, *, @, +, etc.).
     d = Hop count.
     l = Idle time in seconds.
     o = Channel operator level
     r = Real name.
    ---------------------------------------------------------------------
    Examples
    ---------------------------------------------------------------------
    Legacy:     WHO #gaming -n guest*
    -           Shows all users in #gaming, excluding any whose nickname begins with 'guest'.

    Legacy:     WHO * +h staff.example.org
    -           Shows all users on the server with the hostname 'staff.example.org'.

    WHOX:       WHO Coder %uhs
    -           Gets the username, hostname, and server name for the user 'Coder'.

    WHOX:       WHO #support %nf
    -           For everyone in #support, shows their nickname and status flags.
    """
    client.add_flood_penalty(10_000)
    who_mask = '*' if len(recv) <= 1 or recv[1] == '*' else recv[1]

    whox = False
    fields_str = ''
    token = ''

    unique_matches = set()
    for mask in who_mask.split(','):
        unique_matches.update(find_matching_clients(client, mask))
    who_matches = list(unique_matches)

    if len(recv) > 2:
        if '%' in recv[2]:
            whox = True
            params = recv[2].split('%', 1)[1]
            if ',' in params:
                fields_str, token = params.split(',', 1)
                if not token.isdigit() or len(token) > 3:
                    token = ''
            else:
                fields_str = params

        else:
            args = recv[2:]
            arg_idx = 0

            while arg_idx < len(args):
                arg = args[arg_idx]
                if arg.startswith(('+', '-')):
                    is_positive = arg[0] == '+'
                    flags_in_arg = arg[1:]

                    for flag in flags_in_arg:
                        param = ''
                        if flag in 'nhsru':
                            arg_idx += 1
                            if arg_idx < len(args):
                                param = ' '.join(args[arg_idx:])
                                arg_idx = len(args)

                        who_matches = list(filter_clients(who_matches, flag, param, is_positive, client))
                arg_idx += 1

    who_data_list = []
    for who_client in who_matches:
        data = WhoData(who_client)
        data.make(client)
        if whox:
            for char in fields_str:
                process_whox_field(data, char, token, who_mask, client)
        else:
            data.flags = ''  # No longer used, but kept for object compatibility.

        who_data_list.append(data)

    send_who_reply(client, who_data_list, who_mask, whox)


def init(module):
    Isupport.add("WHOX")
    Command.add(module, cmd_who, "WHO")
