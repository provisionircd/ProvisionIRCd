"""
/privmsg and /notice commands
"""

from time import time

from handle.core import Flag, Numeric, Isupport, Command, IRCD, Hook

MAXTARGETS = 8


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
    for result, callback in Hook.call(Hook.CAN_SEND_TO_CHANNEL, args=(client, channel, msg, sendtype)):
        if result == Hook.DENY:
            return 0
    return 1


def send_channel_message(client, channel, message: str, sendtype: str, prefix: str = ''):
    if client.local and client.user and 'o' not in client.user.modes:
        client.local.flood_penalty += len(message) * 200

    oper_override = ''
    if 'n' in channel.modes and not channel.find_member(client):
        if not client.has_permission("channel:override:message:outside"):
            client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "No external messages")
            return
        else:
            oper_override += 'n'

    if 'm' in channel.modes and not channel.client_has_membermodes(client, "vhoaq"):
        if not client.has_permission("channel:override:message:moderated"):
            client.sendnumeric(Numeric.ERR_CANNOTSENDTOCHAN, channel.name, "Cannot send to channel (+m)")
            return
        else:
            oper_override += 'm'

    if client.user and client.local:
        allow = 1
        _msg = message.split(' ')
        hook = Hook.PRE_LOCAL_CHANMSG if sendtype == "PRIVMSG" else Hook.PRE_LOCAL_CHANNOTICE
        for result, callback in Hook.call(hook, args=(client, channel, _msg, prefix)):
            if result == Hook.DENY:
                allow = 0
                break
        if not allow:
            return
        message = ' '.join(_msg)
        if not message.strip():
            return

    broadcast_users = [c for c in channel.clients(prefix=prefix) if c != client and 'd' not in c.user.modes and c.local]

    if not client.is_stealth() and 'u' not in channel.modes:
        for user in [c for c in broadcast_users if not channel.client_has_seen(c, client)]:
            channel.show_join_message(client.mtags, user, client)

    data_prefix = f":{client.fullmask} {sendtype} {channel.name} :"
    step = 510 - len(data_prefix)

    for line in [message[i:i + step] for i in range(0, len(message), step)]:
        broadcast_data = data_prefix + line
        for to_client in broadcast_users:
            to_client.send(client.mtags, broadcast_data)

    data = f":{client.id} {sendtype} {prefix}{channel.name} :{message}"
    IRCD.send_to_servers(client, client.mtags, data)

    if client.user:
        if sendtype == "PRIVMSG":
            hook = Hook.LOCAL_CHANMSG if client.local else Hook.REMOTE_CHANMSG
        else:
            hook = Hook.LOCAL_CHANNOTICE if client.local else Hook.REMOTE_CHANNOTICE
        IRCD.run_hook(hook, client, channel, message, prefix)

    if oper_override and client.user and client.local:
        override_string = f"*** OperOverride: {client.name} ({client.user.username}@{client.user.realhost}) bypassed modes '{oper_override}' on channel {channel.name} with {sendtype}"
        IRCD.log(client, "info", "oper", "OPER_OVERRIDE", override_string, sync=1)

    client.idle_since = int(time())


def send_user_message(client, to_client, message, sendtype: str):
    if client.local and client.user and 'o' not in client.user.modes:
        client.local.flood_penalty += len(message) * 200

    if client.user and to_client.user and client.local:
        allow = 1
        _msg = message.split(' ')
        hook = Hook.PRE_LOCAL_USERMSG if sendtype == "PRIVMSG" else Hook.PRE_LOCAL_USERNOTICE
        for result, callback in Hook.call(hook, args=(client, to_client, _msg)):
            if result == Hook.DENY:
                allow = 0
                break
        if not allow:
            return

        message = ' '.join(_msg)
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
        data = f":{client.id} {sendtype} {to_client.id} :{message}"
        IRCD.send_to_one_server(to_client.uplink, client.mtags, data)

    if client.user:
        if client.local:
            hook = Hook.LOCAL_USERMSG if sendtype == "PRIVMSG" else Hook.LOCAL_USERNOTICE
        else:
            hook = Hook.REMOTE_USERMSG if sendtype == "PRIVMSG" else Hook.REMOTE_USERNOTICE

        IRCD.run_hook(hook, client, to_client, message)

    client.idle_since = int(time())


def cmd_notice(client, recv):
    if len(recv) < 2:
        return client.sendnumeric(Numeric.ERR_NORECIPIENT)

    elif len(recv) < 3:
        return client.sendnumeric(Numeric.ERR_NOTEXTTOSEND)

    targets = recv[1].split(',')
    message = ' '.join(recv[2:]).rstrip().removeprefix(':')

    for target in targets[:MAXTARGETS]:
        if target[0] == '$' and '.' in target and len(target) > 5 \
                and (not client.local or (client.user and client.has_permission("server:broadcast"))):  # and not client.local:
            if client.local:
                client.local.flood_penalty += 500_000
            server_matches = IRCD.find_server_match(target[1:])
            IRCD.new_message(client)
            for server in server_matches:
                if server == IRCD.me:
                    for c in [c for c in IRCD.local_users()]:
                        data = f":{client.fullmask} NOTICE {c.name} :{message}"
                        c.send(client.mtags, data)
                else:
                    data = f":{client.id} NOTICE ${server.name.lower()} :{message}"
                    server.send(client.mtags, data)
            client.mtags = []
            continue

        pre_check_prefix = ''
        target_list = list(target)
        for idx, char in enumerate(target_list[:]):
            if char in IRCD.NICKCHARS:
                break
            if char in IRCD.get_member_prefix_str_sorted():
                pre_check_prefix += char
                del target_list[idx]
        target = ''.join(target_list)

        if target[0] not in IRCD.CHANPREFIXES:
            if not (to_client := IRCD.find_user(target)):
                client.sendnumeric(Numeric.ERR_NOSUCHNICK, target)
                continue

            IRCD.new_message(client)
            if not can_send_to_user(client, to_client, message, sendtype="NOTICE") and not client.ulined:
                client.mtags = []
                continue

            send_user_message(client, to_client, message, sendtype="NOTICE")

        else:
            if not (channel := IRCD.find_channel(target)):
                client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, target)
                continue

            membermodes_sorted = channel.get_membermodes_sorted(reverse=False)
            client_rank = channel.get_sender_rank(client)

            prefix = ''
            for char in pre_check_prefix:
                current_prefix_rank = next(mode.rank for mode in membermodes_sorted if mode.prefix == char)
                if client_rank >= current_prefix_rank or 'o' in client.user.modes:
                    prefix += char
                else:
                    break

            if pre_check_prefix and not prefix:
                continue

            IRCD.new_message(client)
            if not can_send_to_channel(client, channel, message, sendtype="NOTICE", prefix=prefix) and not client.ulined:
                client.mtags = []
                continue

            send_channel_message(client, channel, message, sendtype="NOTICE", prefix=prefix)


def cmd_privmsg(client, recv):
    if len(recv) < 2:
        return client.sendnumeric(Numeric.ERR_NORECIPIENT)

    elif len(recv) < 3:
        return client.sendnumeric(Numeric.ERR_NOTEXTTOSEND)

    targets = recv[1].split(',')

    message = ' '.join(recv[2:]).rstrip().removeprefix(':')
    if not message.strip():
        return client.sendnumeric(Numeric.ERR_NOTEXTTOSEND)

    for target in targets[:MAXTARGETS]:
        if target[0] == '$' and '.' in target and len(target) > 5 \
                and (not client.local or (client.user and client.has_permission("server:broadcast"))):  # and not client.local:
            if client.local:
                client.local.flood_penalty += 500_000
            server_matches = IRCD.find_server_match(target[1:])
            IRCD.new_message(client)
            for server in server_matches:
                if server == IRCD.me:
                    for c in [c for c in IRCD.local_users()]:
                        data = f":{client.fullmask} PRIVMSG {c.name} :{message}"
                        c.send(client.mtags, data)
                else:
                    data = f":{client.id} PRIVMSG ${server.name.lower()} :{message}"
                    server.send(client.mtags, data)
            client.mtags = []
            continue

        pre_check_prefix = ''
        target_list = list(target)
        for idx, char in enumerate(target_list[:]):
            if char in IRCD.NICKCHARS:
                break
            if char in IRCD.get_member_prefix_str_sorted():
                pre_check_prefix += char
                del target_list[idx]
        target = ''.join(target_list)

        if target and target[0] not in IRCD.CHANPREFIXES:
            if not (to_client := IRCD.find_user(target)):
                client.sendnumeric(Numeric.ERR_NOSUCHNICK, target)
                continue

            IRCD.new_message(client)
            if not can_send_to_user(client, to_client, message, sendtype="PRIVMSG") and not client.ulined:
                client.mtags = []
                continue

            send_user_message(client, to_client, message, sendtype="PRIVMSG")

        else:
            if not (channel := IRCD.find_channel(target)):
                client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, target)
                continue

            membermodes_sorted = channel.get_membermodes_sorted(reverse=False)
            client_rank = channel.get_sender_rank(client)

            prefix = ''
            for char in pre_check_prefix:
                current_prefix_rank = next(mode.rank for mode in membermodes_sorted if mode.prefix == char)
                if client_rank >= current_prefix_rank or 'o' in client.user.modes:
                    prefix += char
                else:
                    break

            if pre_check_prefix and not prefix:
                continue

            IRCD.new_message(client)
            if not can_send_to_channel(client, channel, message, "PRIVMSG", prefix) and not client.ulined:
                client.mtags = []
                continue

            send_channel_message(client, channel, message, sendtype="PRIVMSG", prefix=prefix)


def init(module):
    Command.add(module, cmd_privmsg, "PRIVMSG", 2, Flag.CMD_USER)
    Command.add(module, cmd_notice, "NOTICE", 2, Flag.CMD_USER)
    Isupport.targmax("PRIVMSG", MAXTARGETS)
    Isupport.targmax("NOTICE", MAXTARGETS)


def post_load(module):
    Isupport.add("STATUSMSG", ''.join(char for char in IRCD.get_member_prefix_str_sorted() if char not in IRCD.CHANPREFIXES)
                 )
