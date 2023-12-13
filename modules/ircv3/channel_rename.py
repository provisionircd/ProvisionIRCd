"""
/chgcname command
"""

from handle.core import Command, Capability, IRCD, Flag, Numeric
from handle.logger import logging


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
        reason = " ".join(recv[3:])
    else:
        reason = ""

    if not (channel := IRCD.find_channel(recv[1])):
        return IRCD.server_notice(client, f"Channel {name} does not exist.")

    if name[0] != channel.name[0]:
        return IRCD.server_notice(client, 'Converting of channel type is not allowed.')

    if name == channel.name:
        return IRCD.server_notice(client, 'Channel names are equal; nothing changed.')

    if next((c for c in IRCD.get_channels() if c.name == name), 0):
        return IRCD.server_notice(client, f"Unable to change channel name: channel {name} aleady exist.")

    if client.local:
        IRCD.server_notice(client, f'Channel {channel.name} successfully changed to {name}')

    IRCD.send_to_servers(client, f":{client.uid} RENAME {channel.name} {name}")

    old_name = channel.name
    channel.name = name

    for user in [u for u in IRCD.local_users() if channel.find_member(u) and not u.has_capability("draft/channel-rename")]:
        data = f":{user.fullmask} PART {old_name}"
        user.send([], data)
        data = f":{user.fullmask} JOIN {channel.name}"
        user.send([], data)

        Command.do(user, "TOPIC", channel.name)
        Command.do(user, "NAMES", channel.name)

    data = f"RENAME {old_name} {channel.name} :{reason}"
    for user in [u for u in IRCD.local_users() if channel.find_member(u) and u.has_capability("draft/channel-rename")]:
        user.send([], data)

    if client.local:
        msg = f'*** {client.name} ({client.user.username}@{client.user.realhost}) used RENAME to change channel name {old_name} to {name}'
        IRCD.send_snomask(client, 's', msg)


def init(module):
    Command.add(module, cmd_rename, "CHGCNAME", 2, Flag.CMD_USER)
    Command.add(module, cmd_rename, "RENAME", 2, Flag.CMD_USER)
    Capability.add("draft/channel-rename")
