"""
/privmsg and /notice commands
"""

from time import time

from handle.core import IRCD, Command, Flag, Numeric, Isupport, Hook
from handle.logger import logging

MAXTARGETS = 8
OPER_OVERRIDE = ''


def add_oper_override(char):
    global OPER_OVERRIDE
    if char not in OPER_OVERRIDE:
        OPER_OVERRIDE += char


def parse_target(recv_target):
    target = prefix = ''
    member_prefixes = IRCD.get_member_prefix_str_sorted()

    for idx, char in enumerate(recv_target):
        if char in IRCD.CHANCHARS:
            target += recv_target[idx:]
            break
        if char in member_prefixes and char not in IRCD.CHANPREFIXES:
            prefix += char

    if not target or target[0] not in IRCD.CHANPREFIXES:
        target = recv_target

    return target, prefix


def get_lowest_prefix(client, channel, pre_check_prefix):
    if not pre_check_prefix or not (membermodes_sorted := [m for m in channel.get_membermodes_sorted() if m.prefix in pre_check_prefix]):
        return ''

    prefix_rank_map = {m.prefix: m.rank for m in membermodes_sorted}
    prefix_flag_map = {m.prefix: m.flag for m in membermodes_sorted}
    lowest_rank = min(prefix_rank_map.values())
    check_modes = ''.join(prefix_flag_map[prefix] for prefix in pre_check_prefix)

    for m in membermodes_sorted:
        if m.rank == lowest_rank:
            if channel.client_has_membermodes(client, check_modes) or 'o' in client.user.modes:
                return m.prefix
            check_modes = ''.join(prefix_flag_map[p] for p in prefix_rank_map if prefix_rank_map[p] > m.rank)

    return ''


def can_send_to_user(client, user, msg, sendtype):
    if not client.user or not client.local:
        return 1

    for result, callback in Hook.call(Hook.CAN_SEND_TO_USER, args=(client, user, msg, sendtype)):
        if result == Hook.DENY:
            return 0

    return 1


def can_send_to_channel(client, channel, msg, sendtype, prefix=''):
    if not client.user or not client.local:
        return 1

    global OPER_OVERRIDE
    OPER_OVERRIDE = ''

    for result, callback in Hook.call(Hook.CAN_SEND_TO_CHANNEL, args=(client, channel, msg, sendtype)):
        if result == Hook.DENY:
            return 0

    return 1


def send_channel_message(client, channel, message, sendtype, prefix=''):
    global OPER_OVERRIDE

    if client.local and client.user and 'o' not in client.user.modes:
        client.local.flood_penalty += len(message) * 200

    if client.user and client.local:
        msg_parts = message.split(' ')
        hook = Hook.PRE_LOCAL_CHANMSG if sendtype == "PRIVMSG" else Hook.PRE_LOCAL_CHANNOTICE

        for result, _ in Hook.call(hook, args=(client, channel, msg_parts, prefix)):
            if result == Hook.DENY:
                return

        message = ' '.join(msg_parts)
        if not message.strip():
            return

    broadcast_users = [c for c in channel.clients(prefix=prefix) if c != client and 'd' not in c.user.modes and c.local]

    if not client.is_stealth() and 'u' not in channel.modes:
        for user in [c for c in broadcast_users if not channel.client_has_seen(c, client)]:
            channel.show_join_message(client.mtags, user, client)

    data_prefix = f":{client.fullmask} {sendtype} {prefix}{channel.name} :"
    step = 510 - len(data_prefix)

    for line in [message[i:i + step] for i in range(0, len(message), step)]:
        broadcast_data = data_prefix + line
        for to_client in broadcast_users:
            to_client.send(client.mtags, broadcast_data)

    IRCD.send_to_servers(client, client.mtags, f":{client.id} {sendtype} {prefix}{channel.name} :{message}")

    if client.user:
        if sendtype == "PRIVMSG":
            hook = Hook.LOCAL_CHANMSG if client.local else Hook.REMOTE_CHANMSG
        else:
            hook = Hook.LOCAL_CHANNOTICE if client.local else Hook.REMOTE_CHANNOTICE
        IRCD.run_hook(hook, client, channel, message, prefix)

    if OPER_OVERRIDE and client.user and client.local:
        IRCD.send_oper_override(client, f"bypassed modes '{OPER_OVERRIDE}' on channel {channel.name} with {sendtype}")

    client.idle_since = int(time())


def send_user_message(client, to_client, message, sendtype):
    if client.local and client.user and 'o' not in client.user.modes:
        client.local.flood_penalty += len(message) * 200

    if client.user and to_client.user and client.local:
        msg_parts = message.split(' ')
        hook = Hook.PRE_LOCAL_USERMSG if sendtype == "PRIVMSG" else Hook.PRE_LOCAL_USERNOTICE

        for result, _ in Hook.call(hook, args=(client, to_client, msg_parts)):
            if result == Hook.DENY:
                return

        message = ' '.join(msg_parts)
        if not message.strip():
            return

    if to_client.user.away:
        client.sendnumeric(Numeric.RPL_AWAY, to_client.name, to_client.user.away)

    if to_client.local:
        data_prefix = f":{client.fullmask} {sendtype} {to_client.name} :"
        step = 510 - len(data_prefix)

        for line in [message[i:i + step] for i in range(0, len(message), step)]:
            data = data_prefix + line
            to_client.send(client.mtags, data)

    else:
        IRCD.send_to_one_server(to_client.uplink, client.mtags, f":{client.id} {sendtype} {to_client.id} :{message}")

    if client.user:
        if client.local:
            hook = Hook.LOCAL_USERMSG if sendtype == "PRIVMSG" else Hook.LOCAL_USERNOTICE
        else:
            hook = Hook.REMOTE_USERMSG if sendtype == "PRIVMSG" else Hook.REMOTE_USERNOTICE

        IRCD.run_hook(hook, client, to_client, message)

    client.idle_since = int(time())


def process_server_broadcast(client, target, message, sendtype):
    """Process a server broadcast message ($server)."""
    if not (target.startswith('$') and '.' in target and len(target) > 5 and client.has_permission("server:broadcast")):
        return 0

    if client.local:
        client.local.flood_penalty += 500_000

    server_matches = IRCD.find_server_match(target[1:])
    IRCD.new_message(client)

    for server in server_matches:
        if server == IRCD.me:
            for c in IRCD.get_clients(local=1, user=1):
                c.send(client.mtags, f":{client.fullmask} {sendtype} {c.name} :{message}")
        else:
            server.send(client.mtags, f":{client.id} {sendtype} ${server.name.lower()} :{message}")

    client.mtags = []
    return 1


def process_message(client, targets, message, sendtype):
    for target in targets[:MAXTARGETS]:
        if process_server_broadcast(client, target, message, sendtype):
            continue

        parsed_target, prefix = parse_target(target)

        if parsed_target[0] not in IRCD.CHANPREFIXES:
            target_nick, _, target_host = parsed_target.partition('@')

            if not (to_client := IRCD.find_client(target_nick, user=1)) or (target_host and target_host.lower() != to_client.uplink.name.lower()):
                client.sendnumeric(Numeric.ERR_NOSUCHNICK, parsed_target)
                continue

            IRCD.new_message(client)
            if not can_send_to_user(client, to_client, message, sendtype) and not client.is_uline():
                client.mtags = []
                continue

            send_user_message(client, to_client, message, sendtype)

        else:
            if not (channel := IRCD.find_channel(parsed_target)):
                client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, parsed_target)
                continue

            usable_prefix = get_lowest_prefix(client, channel, prefix)
            if prefix and not usable_prefix:
                continue

            IRCD.new_message(client)
            if not can_send_to_channel(client, channel, message, sendtype, usable_prefix) and not client.is_uline():
                client.mtags = []
                continue

            send_channel_message(client, channel, message, sendtype, usable_prefix)


def do_msg(client, recv, sendtype):
    if len(recv) < 2:
        return client.sendnumeric(Numeric.ERR_NORECIPIENT)

    if len(recv) < 3:
        return client.sendnumeric(Numeric.ERR_NOTEXTTOSEND)

    targets = recv[1].split(',')
    message = ' '.join(recv[2:]).rstrip().removeprefix(':')

    if sendtype == "PRIVMSG" and not message.strip():
        return client.sendnumeric(Numeric.ERR_NOTEXTTOSEND)

    process_message(client, targets, message, sendtype)


def cmd_privmsg(client, recv):
    do_msg(client, recv, "PRIVMSG")


def cmd_notice(client, recv):
    do_msg(client, recv, "NOTICE")


def init(module):
    Command.add(module, cmd_privmsg, "PRIVMSG", 2, Flag.CMD_USER)
    Command.add(module, cmd_notice, "NOTICE", 2, Flag.CMD_USER)
    Isupport.targmax("PRIVMSG", MAXTARGETS)
    Isupport.targmax("NOTICE", MAXTARGETS)


def post_load(module):
    statusmsg = ''.join(char for char in IRCD.get_member_prefix_str_sorted() if char not in IRCD.CHANPREFIXES)
    Isupport.add("STATUSMSG", statusmsg)
