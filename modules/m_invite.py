"""
/invite command
"""

import time

from handle.core import IRCD, Command, Channelmode, Capability, Flag, Numeric, Hook


def cmd_invite(client, recv):
    """
    Invites a user to a channel.
    Syntax: /INVITE <user> <channel>
    """

    oper_override = 0

    if not (invite_client := IRCD.find_client(recv[1], user=1)):
        return client.sendnumeric(Numeric.ERR_NOSUCHNICK, recv[1])

    if not (channel := IRCD.find_channel(recv[2])):
        return client.sendnumeric(Numeric.ERR_NOSUCHCHANNEL, recv[2])

    if not channel.find_member(client):
        if invite_client == client and not client.has_permission("channel:override:invite:self"):
            return client.sendnumeric(Numeric.ERR_NOTONCHANNEL, channel.name)
        elif not client.has_permission("channel:override:invite:notinchannel"):
            return client.sendnumeric(Numeric.ERR_NOTONCHANNEL, channel.name)
        else:
            oper_override = 1

    if 'V' in channel.modes:
        if not channel.client_has_membermodes(client, 'q') and not client.has_permission("channel:override:invite:no-invite"):
            return client.sendnumeric(Numeric.ERR_NOINVITE, channel.name)
        elif client.has_permission("channel:override:invite:no-invite"):
            oper_override = 1

    if channel.find_member(invite_client):
        return client.sendnumeric(Numeric.ERR_USERONCHANNEL, invite_client.name, channel.name)

    if (inv := channel.get_invite(invite_client)) and inv.by == client:
        return

    invite_can_override = 1 if (client.has_permission("channel:override:invite") or channel.client_has_membermodes(client, "oaq")) else 0
    channel.add_invite(to=invite_client, by=client, override=invite_can_override)
    if oper_override and client.user and client.local:
        overrides = {
            'b': " [Overriding +b]" if channel.is_banned(invite_client) else '',
            'i': " [Overriding +i]" if 'i' in channel.modes else '',
            'l': " [Overriding +l]" if 'l' in channel.modes and channel.membercount >= channel.limit else '',
            'k': " [Overriding +k]" if 'k' in channel.modes else '',
            'R': " [Overriding +R]" if 'R' in channel.modes and 'r' not in invite_client.user.modes else '',
            'z': " [Overriding +z]" if 'z' in channel.modes and 'z' not in invite_client.user.modes else ''
        }
        s = next((msg for key, msg in overrides.items() if msg), '')
        IRCD.send_oper_override(client, f"INVITE {invite_client.name} {channel.name}{s}")

    data = f":{client.fullmask} INVITE {invite_client.name} {channel.name}"
    invite_client.send([], data)
    client.sendnumeric(Numeric.RPL_INVITING, invite_client.name, channel.name)

    broadcast_users = [c for c in channel.clients(client_cap="invite-notify") if c.local
                       and (channel.client_has_membermodes(c, "hoaq") or c.has_permission("channel:see:invites"))]

    for user in broadcast_users:
        user.send([], data)

    # Users who do not have the invite-notify capability should still receive a traditional notice.
    notice_users = [c for c in channel.clients() if c.local and c not in broadcast_users
                    and (channel.client_has_membermodes(c, "hoaq") or c.has_permission("channel:see:invites"))]
    broadcast_data = (f"NOTICE {channel.name} :{client.name} ({client.user.username}@{client.user.host}) "
                      f"has invited {invite_client.name} to join the channel")
    for notice_user in notice_users:
        IRCD.server_notice(notice_user, broadcast_data)

    IRCD.send_to_servers(client, [], f":{client.id} INVITE {invite_client.name} {channel.name}")


def expired_invites():
    # Expire invites after 1 hour.
    for chan in IRCD.get_channels():
        chan.invites = [invite for invite in chan.invites if time.time() - invite.when < 3600.0]


def invite_can_join(client, channel, key):
    if 'i' in channel.modes and not channel.is_invex(client):
        return Numeric.ERR_INVITEONLYCHAN
    return 0


def init(module):
    Hook.add(Hook.LOOP, expired_invites)
    Hook.add(Hook.CAN_JOIN, invite_can_join)
    Cmode_i = Channelmode()
    Cmode_i.flag = 'i'
    Cmode_i.desc = "You need to be invited to join the channel"
    Cmode_i.paramcount = 0
    Cmode_i.is_ok = Channelmode.allow_chanop
    Channelmode.add(module, Cmode_i)
    Command.add(module, cmd_invite, "INVITE", 2, Flag.CMD_USER)
    Capability.add("invite-notify")
