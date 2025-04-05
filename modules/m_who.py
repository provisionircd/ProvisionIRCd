"""
/who command
"""

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


def send_who_reply(client, who_data_list, mask):
    for data in who_data_list:
        if any(data.fields):
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
    if flag == 'n':  # Nickname filter
        matches = (c for c in IRCD.get_clients(user=1, registered=1) if is_match(flag_match.lower(), c.name.lower()))
    elif flag == 'u':  # Username filter
        matches = (c for c in IRCD.get_clients(user=1, registered=1) if is_match(flag_match.lower(), c.user.username.lower()))
    elif flag == 'h' and client and 'o' in client.user.modes:  # Host filter (operators only)
        matches = (c for c in IRCD.get_clients(user=1, registered=1) if is_match(flag_match.lower(), c.user.realhost.lower()))
    elif flag == 'i' and client and 'o' in client.user.modes:  # IP filter (operators only)
        matches = (c for c in IRCD.get_clients(user=1, registered=1) if is_match(flag_match, c.ip))
    elif flag == 's' and client and 'o' in client.user.modes:  # Server filter (operators only)
        matches = (c for c in IRCD.get_clients(user=1, registered=1) if is_match(flag_match.lower(), c.uplink.name.lower()))
    elif flag == 'r':  # Realname filter
        matches = (c for c in IRCD.get_clients(user=1, registered=1) if is_match(flag_match.lower(), c.info.lower()))
    elif flag == 'a':  # Account filter
        matches = (c for c in IRCD.get_clients(user=1, registered=1) if is_match(flag_match.lower(), c.user.account.lower()))
    else:
        return clients

    if flag_true:
        return matches
    else:
        matches = set(matches)
        return (c for c in clients if c not in matches)


def process_whox_field(data, flag, token, mask, client):
    """ Process a single WHOX field for a client. """
    who_client = data.who_client

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
        data.fields[9] = str(who_client.idle_since)
    elif flag == 'a':
        account = who_client.user.account
        data.fields[10] = account if account != '*' else '0'
    elif flag == 'o':
        if who_channel := IRCD.find_channel(mask):
            status = ''.join(m.prefix for m in who_channel.get_membermodes_sorted()
                             if who_channel.client_has_membermodes(who_client, m.flag))
            data.fields[11] = status
    elif flag == 'r':
        data.fields[12] = ':' + who_client.info


def find_matching_clients(client, mask):
    if chan := IRCD.find_channel(mask):
        if 's' in chan.modes and not chan.find_member(client) and not client.has_permission("channel:see:who:secret"):
            return []

        return (c for c in chan.clients() if chan.user_can_see_member(client, c)
                and ('i' not in c.user.modes or chan.find_member(client) or client.has_permission("channel:see:who:invisible")))

    if (user := IRCD.find_client(mask)) and user.registered:
        return [user]

    return (c for c in IRCD.get_clients(user=1, registered=1) if is_match(mask, c.ip)
            and ('i' not in c.user.modes or IRCD.common_channels(client, c)
                 or client.has_permission("channel:see:who:invisible") or c == client))


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

    client.add_flood_penalty(10_000)
    who_mask = '*' if len(recv) <= 1 or recv[1] == '*' else recv[1]

    flags = ''
    flag_true = 1
    flag_matches = []
    token = ''
    whox = False

    if len(recv) > 2:
        flag_arg = recv[2]
        if flag_arg.startswith('+'):
            flags = flag_arg[1:]
        elif flag_arg.startswith('-'):
            flag_true = 0
            flags = flag_arg[1:]
        else:
            flags = flag_arg

        # Handle WHOX format
        if '%' in flags:
            whox = True
            if ',' in flags:
                token = flags.split(',', 1)[1]

    if len(recv) > 3:
        flag_matches = recv[3:]

    for mask in who_mask.split(','):
        who_matches = find_matching_clients(client, mask)

        flag_match_idx = -1
        for char in flags:
            # Skip WHOX indicator
            if char == '%':
                continue

            flag_match_idx += 1
            flag_match = flag_matches[flag_match_idx] if flag_match_idx < len(flag_matches) else ''

            if char == 'm' and 'o' in client.user.modes:
                condition = '-' if mask.startswith('-') else '+'
                mode_mask = mask[1:] if condition == '-' else mask

                filtered = []
                for mode in mode_mask:
                    for c in IRCD.get_clients(user=1, registered=1):
                        if (((condition == '+' and mode in c.user.modes)
                             or (condition == '-' and mode not in c.user.modes))
                                and c not in filtered):
                            filtered.append(c)

                who_matches = filtered if flag_true else [c for c in who_matches if c not in filtered]

            elif char == 'd' and mask.isdigit():
                who_matches = (c for c in IRCD.get_clients(user=1, registered=1) if c.hopcount == int(mask))

            elif not whox:
                who_matches = filter_clients(who_matches, char, flag_match, flag_true, client)

        who_data_list = []
        for who_client in who_matches:
            data = WhoData(who_client)
            data.flags = flags
            data.make(client)

            if whox:
                for char in flags:
                    process_whox_field(data, char, token, mask, client)

            who_data_list.append(data)

        send_who_reply(client, who_data_list, mask)


def init(module):
    Isupport.add("WHOX")
    Command.add(module, cmd_who, "WHO")
