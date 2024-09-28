"""
/sajoin and /sapart command
"""

from handle.core import IRCD, Command, Numeric, Flag


def cmd_sajoinpart(client, recv):
    if not (Command.find_command(client, "PART")) or not (Command.find_command(client, "JOIN")):
        return

    if not (target := IRCD.find_user(recv[1])):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    cmd = recv[0].lower()
    if client.local:
        permission_check = f"sacmds:{cmd}:global" if not target.local else f"sacmds:{cmd}:local"

        if not client.has_permission(permission_check):
            return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

        if 'S' in target.user.modes or target.ulined or target.is_service:
            return IRCD.server_notice(client, f"*** You cannot use /{cmd.upper()} on services.")

        client.local.flood_penalty += 100_000

    chan = IRCD.strip_format(recv[2])
    if not (channel := IRCD.find_channel(chan)):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, chan)

    if channel.name[0] == '&':
        return IRCD.server_notice(client, f"*** You cannot use /{cmd.upper()} on local channels.")

    if cmd == "sapart" and target not in channel.clients():
        return client.sendnumeric(Numeric.ERR_USERNOTINCHANNEL, target.name, channel.name)

    if cmd == "sajoin" and target in channel.clients():
        return client.sendnumeric(Numeric.ERR_USERONCHANNEL, target.name, channel.name)

    what = "join" if cmd == "sajoin" else "part"
    if what == "join" and target.local:
        target.add_flag(Flag.CLIENT_USER_SAJOIN)
        Command.do(target, "JOIN", channel.name)
        target.flags.remove(Flag.CLIENT_USER_SAJOIN)
    elif target.local:
        Command.do(target, "PART", channel.name)
    data = f":{client.id} SA{what.upper()} {target.name} {channel.name}"
    IRCD.send_to_servers(client, [], data)

    rootevent = cmd
    event = "LOCAL_" if target.local else "REMOTE_"
    event += rootevent.upper()
    msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) used {cmd.upper()} to make {target.name} {what} {channel.name}"
    IRCD.log(client, "info", rootevent, event, msg, sync=0)

    if target.local:
        msg = f"*** Your were forced to {what} {channel.name}."
        IRCD.server_notice(target, msg)


def init(module):
    Command.add(module, cmd_sajoinpart, "SAJOIN", 2, Flag.CMD_OPER)
    Command.add(module, cmd_sajoinpart, "SAPART", 2, Flag.CMD_OPER)
