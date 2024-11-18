"""
/sajoin and /sapart command
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_sajoinpart(client, recv):
    if not (Command.find_command(client, "PART")) or not (Command.find_command(client, "JOIN")):
        return

    cmd = recv[0].lower()
    if not client.has_permission(f"sacmds:{cmd}:local") and not client.has_permission(f"sacmds:{cmd}:global"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    if client.local:
        permission_check = f"sacmds:{cmd}:global" if not target.local else f"sacmds:{cmd}:local"

        if not client.has_permission(permission_check) and not client.has_permission(f"sacmds:{cmd}:global"):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

        if 'S' in target.user.modes or target.ulined or target.is_service:
            return IRCD.server_notice(client, f"*** You cannot use /{cmd.upper()} on services.")

        client.local.flood_penalty += 50_000

    chan = IRCD.strip_format(recv[2])
    if not (channel := IRCD.find_channel(chan)):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, chan)

    if channel.name[0] == '&':
        return IRCD.server_notice(client, f"*** You cannot use /{cmd.upper()} on local channels.")

    if (cmd == "sapart" and not channel.find_member(target)) or (cmd == "sajoin" and channel.find_member(target)):
        error = Numeric.ERR_USERNOTINCHANNEL if cmd == "sapart" else Numeric.ERR_USERONCHANNEL
        return client.sendnumeric(error, target.name, channel.name)

    what = "join" if cmd == "sajoin" else "part"
    if target.local:
        if what == "join":
            target.add_flag(Flag.CLIENT_USER_SAJOIN)
            Command.do(target, "JOIN", channel.name)
            target.flags.remove(Flag.CLIENT_USER_SAJOIN)
        else:
            Command.do(target, "PART", channel.name)

    data = f":{client.id} SA{what.upper()} {target.name} {channel.name}"
    IRCD.send_to_servers(client, [], data)

    event = f"{'LOCAL' if target.local else 'REMOTE'}_{cmd.upper()}"
    msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) used {cmd.upper()} to make {target.name} {what} {channel.name}"
    IRCD.log(client, "info", cmd, event, msg, sync=1 if target.local else 0)

    if target.local:
        IRCD.server_notice(target, f"*** Your were forced to {what} {channel.name}.")


def init(module):
    Command.add(module, cmd_sajoinpart, "SAJOIN", 2, Flag.CMD_OPER)
    Command.add(module, cmd_sajoinpart, "SAPART", 2, Flag.CMD_OPER)
