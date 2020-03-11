"""
/invite command
"""

import ircd

from modules.m_joinpart import checkMatch
import time


class chmode_i(ircd.ChannelMode):
    def __init__(self):
        self.mode = 'i'
        self.desc = 'You need to be invited to join the channel'
        self.type = 3


@ircd.Modules.command
class Invite(ircd.Command):
    """
    Invites a user to a channel.
    Syntax: /INVITE <user> <channel>
    """
    def __init__(self):
        self.command = 'invite'
        self.params = 2
        self.support = [('INVEX',)]
        self.server_support = 1

    def execute(self, client, recv, override=False):
        if type(client).__name__ == 'Server':
            override = True
            sourceServer = client
            client = [u for u in self.ircd.users if u.uid == recv[0][1:]][0]
            recv = recv[1:]
        else:
            sourceServer = client.server

        oper_override = False

        invite_user = [u for u in self.ircd.users if u.nickname.lower() == recv[1].lower() or u.uid.lower() == recv[1].lower()]

        if not invite_user:
            return client.sendraw(self.ERR.NOSUCHNICK, '{} :No such nick'.format(recv[1]))

        invite_user = invite_user[0]

        channel = [c for c in self.ircd.channels if c.name.lower() == recv[2].lower()]

        if not channel:
            return client.sendraw(self.ERR.NOSUCHCHANNEL, '{} :No such channel'.format(recv[2]))

        channel = channel[0]

        if client not in channel.users:
            if not override and not client.ocheck('o', 'override'):
                return client.sendraw(self.ERR.NOTONCHANNEL, '{} :You are not on that channel'.format(channel.name))
            else:
                oper_override = True

        if client.chlevel(channel) < 3:
            if not client.ocheck('o', 'override'):
                return client.sendraw(self.ERR.CHANOPRIVSNEEDED, '{} :You are not a channel half-operator'.format(channel.name))
            else:
                oper_override = True

        if 'V' in channel.modes:
            if not client.ocheck('o', 'override'):
                return client.sendraw(self.ERR.NOINVITE, ':Invite is disabled on channel {} (+V)'.format(channel.name))
            else:
                oper_override = True

        if invite_user in channel.users:
            return client.sendraw(self.ERR.USERONCHANNEL, '{} :is already on channel {}'.format(invite_user.nickname, channel.name))

        if invite_user in channel.invites and not client.ocheck('o', 'override'):
            return client.sendraw(342, '{} :has already been invited to {}'.format(invite_user.nickname, channel.name))

        channel.invites[invite_user] = {}
        channel.invites[invite_user]['ctime'] = int(time.time())
        channel.invites[invite_user]['override'] = True if (client.ocheck('o', 'override') or client.chlevel(channel) >= 3) else False
        if oper_override:
            s = ''
            if checkMatch(invite_user, self.ircd, 'b', channel):
                s = ' [Overriding +b]'
            elif 'i' in channel.modes:
                s = ' [Overriding +i]'
            elif 'l' in channel.modes and len(channel.users) >= channel.limit:
                s = ' [Overriding +l]'
            elif 'k' in channel.modes:
                s = ' [Overriding +k]'
            elif 'R' in channel.modes and 'r' not in invite_user.modes:
                s = ' [Overriding +R]'
            elif 'z' in channel.modes and 'z' not in invite_user.modes:
                s = ' [Overriding +z]'
            self.ircd.snotice('s', '*** OperOverride by {} ({}@{}) with INVITE {} {}{}'.format(client.nickname, client.ident, client.hostname, invite_user.nickname, channel.name, s))

        client.broadcast([invite_user], 'INVITE {} {}'.format(invite_user.nickname, channel.name))
        client.sendraw(self.RPL.INVITING, '{} {}'.format(invite_user.nickname, channel.name))
        data = ':{} INVITE {} {}'.format(client.uid, invite_user.nickname, channel.name)
        p = {'s_sync': False}
        self.ircd.handle('NOTICE', '{} :{} ({}@{}) invited {} to join the channel'.format(channel.name, user.nickname, user.ident, user.hostname, invite_user.nickname), params=p)
        self.ircd.new_sync(self.ircd, sourceServer, data)



@ircd.Modules.hooks.loop()
def expired_invites(ircd):
    ### Expire all invites after 6 hours.
    for chan in [channel for channel in ircd.channels if len(channel.invites) > 0]:
        for invite in dict(chan.invites):
            if time.time() - chan.invites[invite]['ctime'] > 3600.0*6:
                del chan.invites[invite]
