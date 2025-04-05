"""
/chgcname command
"""

from handle.core import IRCD, Command, Capability, Flag, Numeric


# https://ircv3.net/specs/extensions/channel-rename


class RenameData:
    # Keep track of when a channel was renamed.
    # Used to prevent excessive renaming and notifying users that weren't present
    # during the rename that the channel was renamed.
    timestamps = {}


def cmd_rename(client, recv):
    """
    Change channel name capitalisation.
    Example: /RENAME #home #Home
    """

    if not client.has_permission("channel:rename"):
        return client.sendnumeric(Numeric.ERR_NOPRIVILEGES)

    name = recv[2]

    if len(recv) > 2:
        reason = ' '.join(recv[3:])
    else:
        reason = ''

    if not (channel := IRCD.find_channel(recv[1])):
        return IRCD.server_notice(client, f"Channel {name} does not exist.")

    if name[0] != channel.name[0]:
        return IRCD.server_notice(client, "Converting of channel type is not allowed.")

    if name == channel.name:
        return IRCD.server_notice(client, "Channel names are equal; nothing changed.")

    if next((c for c in IRCD.get_channels() if c.name == name), 0):
        return IRCD.server_notice(client, f"Unable to change channel name: channel {name} aleady exist.")

    if client.local:
        IRCD.server_notice(client, f"Channel {channel.name} successfully changed to {name}")

    IRCD.send_to_servers(client, [], f":{client.id} RENAME {channel.name} {name}")

    old_name = channel.name
    channel.name = name

    for user in [u for u in IRCD.get_clients(local=1) if channel.find_member(u) and not u.has_capability("draft/channel-rename")]:
        user.send([], f":{user.fullmask} PART {old_name}")
        user.send([], f":{user.fullmask} JOIN {channel.name}")

        Command.do(user, "TOPIC", channel.name)
        Command.do(user, "NAMES", channel.name)

    for user in [u for u in IRCD.get_clients(local=1, cap="draft/channel-rename") if channel.find_member(u)]:
        user.send([], f"RENAME {old_name} {channel.name} :{reason}")

    if client.local:
        msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) used RENAME to change channel name {old_name} to {name}"
        IRCD.send_snomask(client, 's', msg)


def init(module):
    Command.add(module, cmd_rename, "CHGCNAME", 2, Flag.CMD_USER)
    Command.add(module, cmd_rename, "RENAME", 2, Flag.CMD_USER)
    Capability.add("draft/channel-rename")
