"""
/privmsg and /notice commands
"""

import ircd

from handle.functions import match, checkSpamfilter, logging

import time
import re

MAXTARGETS = 20


class Privmsg(ircd.Command):
    """
    Send a direct message to a channel or user.
    Syntax: PRIVMSG <target> <msg>
    """
    def __init__(self):
        self.command = ['privmsg', 'msg']
        self.support = [('MAXTARGETS', MAXTARGETS)]


    def execute(self, client, recv, override=False):
        #print(f": /privmsg: {client} :: {recv}")
        if type(client).__name__ == 'Server':
            sourceServer = client
            sourceID = client.sid
            override = 1
            if client != self.ircd:
                S = recv[0][1:]
                source = [s for s in self.ircd.servers+[self.ircd] if s.sid == S or s.hostname == S]+[u for u in self.ircd.users if u.uid == S or u.nickname == S]
                client = source[0]
                sourceID = client.uid if type(client).__name__ == 'User' else client.sid
            recv = recv[1:]
            recv = self.ircd.parse_command(' '.join(recv[0:]))
        else:
            sourceServer = client.server
            sourceID = client.uid
            if client.ocheck('o', 'override'):
                override = 1

        if len(recv) < 2:
            return client.sendraw(self.ERR.NORECIPIENT, ':No recipient given')

        elif len(recv) < 3:
            return client.sendraw(self.ERR.NOTEXTTOSEND, ':No text to send')

        targets = recv[1].split(',')

        msg = ' '.join(recv[2:]).rstrip()

        if type(client).__name__ == 'User':
            client.flood_penalty += len(msg) * 150

        for target in targets[:MAXTARGETS]:
            if target[0] not in self.ircd.chantypes:
                user = list(filter(lambda u: u.nickname.lower() == target.lower() or u.uid.lower() == target.lower(), self.ircd.users))

                if not user:
                    client.sendraw(401, '{} :No such nick'.format(target))
                    continue
                user = user[0]

                if type(client).__name__ == 'User' and checkSpamfilter(client, self.ircd, user.nickname, 'private', msg):
                    continue

                if type(client).__name__ == 'User' and client.server == self.ircd:
                    block_msg = 0
                    for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'pre_usermsg']:
                        try:
                            mod_msg = callable[2](client, self.ircd, user, msg)
                            if mod_msg:
                                msg = mod_msg
                            elif not mod_msg and mod_msg is not None:
                                block_msg = 1
                                break
                        except Exception as ex:
                            logging.exception(ex)
                    if block_msg:
                        continue

                if user.away:
                    client.sendraw(self.RPL.AWAY, '{} :{}'.format(user.nickname, user.away))

                if type(client).__name__ == 'User':
                    client.broadcast([user], 'PRIVMSG {} :{}'.format(user.nickname, msg))
                    client.idle = int(time.time())
                    if 'echo-message' in client.caplist:
                        client._send(':{} PRIVMSG {} :{}'.format(client.fullmask(), user.nickname, msg))

                if user.server != self.ircd:
                    data = ':{} PRIVMSG {} :{}'.format(sourceID, user.nickname, msg)
                    self.ircd.new_sync(self.ircd, sourceServer, data, direct=user.server)


            else:
                channel = [channel for channel in self.ircd.channels if channel.name.lower() == target.lower()]

                if not channel:
                    client.sendraw(self.ERR.NOSUCHCHANNEL, '{} :No such channel'.format(target))
                    continue

                channel = channel[0]
                if type(client).__name__ == 'User' and checkSpamfilter(client, self.ircd, channel.name, 'channel', msg):
                    continue

                if not override:
                    if client not in channel.users and 'n' in channel.modes and not override:
                        client.sendraw(self.ERR.CANNOTSENDTOCHAN, '{} :No external messages'.format(channel.name))
                        continue

                    if 'C' in channel.modes and (msg[0] == '' and msg[-1] == '') and msg.split()[0] != 'ACTION' and client.chlevel(channel) < 5 and not override:
                        client.sendraw(self.ERR.CANNOTSENDTOCHAN, '{} :CTCPs are not permitted in this channel'.format(channel.name))
                        continue

                    if 'm' in channel.modes and client.chlevel(channel) == 0 and not override:
                        client.sendraw(self.ERR.CANNOTSENDTOCHAN, '{} :Cannot send to channel (+m)'.format(channel.name))
                        continue


                if type(client).__name__ == 'User' and client.server == self.ircd:
                    block_msg = 0
                    for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'pre_chanmsg']:
                        try:
                            mod_msg = callable[2](client, self.ircd, channel, msg)
                            if mod_msg:
                                msg = mod_msg
                            elif not mod_msg and mod_msg is not None:
                                block_msg = 1
                                break
                        except Exception as ex:
                            logging.exception(ex)
                    if block_msg:
                        continue

                users = [user for user in channel.users if user != client and 'd' not in user.modes]
                client.broadcast(users, 'PRIVMSG {} :{}'.format(channel.name, msg))
                if type(client).__name__ == 'User' and 'echo-message' in client.caplist and 'd' not in client.modes:
                    client._send(':{} PRIVMSG {} :{}'.format(client.fullmask(), channel.name, msg))

                client.idle = int(time.time())
                self.ircd.new_sync(self.ircd, sourceServer, ':{} PRIVMSG {} :{}'.format(sourceID, target, msg))

                ### Check for module hooks (channel messages).
                if type(client).__name__ == 'User':
                    for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'chanmsg']:
                        try:
                            callable[2](client, self.ircd, channel, msg)
                        except Exception as ex:
                            logging.exception(ex)



@ircd.Modules.command
class Notice(ircd.Command):
    """
    Send a direct notice to a channel or user.
    Syntax: NOTICE <target> <msg>
    """

    def __init__(self):
        self.command = 'notice'

    def execute(self, client, recv, override=False, s_sync=True):
        if type(client).__name__ == 'Server':
            sourceServer = client
            S = recv[0][1:]
            source = [s for s in self.ircd.servers+[self.ircd] if s.sid == S or s.hostname == S]+[u for u in self.ircd.users if u.uid == S or u.nickname == S]
            if not source:
                return
            client = source[0]
            sourceID = client.uid if type(client).__name__ == 'User' else client.sid
            recv = recv[1:]

            recv = self.ircd.parse_command(' '.join(recv[0:]))

        else:
            sourceServer = client.server
            sourceID = client.uid
            if client.ocheck('o', 'override'):
                override = True

        if len(recv) < 2:
            return client.sendraw(self.ERR.NORECIPIENT, ':No recipient given')

        elif len(recv) < 3:
            return client.sendraw(self.ERR.NOTEXTTOSEND, ':No text to send')

        global msg
        msg = ' '.join(recv[2:])

        if type(client).__name__ == 'User':
            client.flood_penalty += len(msg) * 150

        for target in recv[1].split(',')[:MAXTARGETS]:
            if target[0] == '$' and sourceServer != self.ircd:
                server = list(filter(lambda s: s.hostname.lower() == target[1:].lower(), self.ircd.servers+[self.ircd]))[0]
                if server == self.ircd:
                    for user in (user for user in self.ircd.users if user.server == server):
                        client.broadcast([user], 'NOTICE ${} :{}'.format(server.hostname.lower(), msg))
                else:
                    for s in (s for s in self.ircd.servers if s != sourceServer):
                        s._send(':{} NOTICE ${} :{}'.format(sourceID, server.hostname.lower(), msg))

            elif target[0] not in self.ircd.chantypes:
                user = list(filter(lambda u: u.nickname.lower() == target.lower() or u.uid.lower() == target.lower(), self.ircd.users))
                if not user:
                    client.sendraw(self.ERR.NOSUCHNICK, '{} :No such user'.format(target))
                    continue
                user = user[0]
                if type(client).__name__ == 'User' and checkSpamfilter(client, self.ircd, user.nickname, 'private', msg):
                    continue


                if type(client).__name__ == 'User' and client.server == self.ircd:
                    block_msg = 0
                    for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'pre_usernotice']:
                        try:
                            mod_msg = callable[2](client, self.ircd, user, msg)
                            if mod_msg:
                                msg = mod_msg
                            elif not mod_msg and mod_msg is not None:
                                block_msg = 1
                                break
                        except Exception as ex:
                            logging.exception(ex)
                    if block_msg:
                        continue

                if user.server != self.ircd:
                    self.ircd.new_sync(self.ircd, sourceServer, ':{} NOTICE {} :{}'.format(sourceID, target, msg, direct=user.server))
                else:
                    client.broadcast([user], 'NOTICE {} :{}'.format(user.nickname, msg))

            else:
                channel = list(filter(lambda c: c.name.lower() == target.lower(), self.ircd.channels))

                if not channel:
                    client.sendraw(self.ERR.NOSUCHCHANNEL, '{} :No such channel'.format(target))
                    continue

                channel = channel[0]

                if client not in channel.users and len(channel.users) > 0 and 'n' in channel.modes and not override:
                    client.sendraw(self.ERR.CANNOTSENDTOCHAN, '{} :No external messages'.format(channel.name))
                    continue

                if 'T' in channel.modes and client.chlevel(channel) < 5 and not override:
                    client.sendraw(self.ERR.CANNOTSENDTOCHAN, '{} :NOTICEs are not permitted in this channel'.format(channel.name))
                    continue

                if type(client).__name__ == 'User' and checkSpamfilter(client, self.ircd, channel.name, 'channel', msg):
                    continue


                if type(client).__name__ == 'User' and client.server == self.ircd:
                    block_msg = 0
                    for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'pre_channotice']:
                        try:
                            mod_msg = callable[2](client, self.ircd, channel, msg)
                            if mod_msg:
                                msg = mod_msg
                            elif not mod_msg and mod_msg is not None:
                                block_msg = 1
                                break
                        except Exception as ex:
                            logging.exception(ex)
                    if block_msg:
                        continue

                    client.broadcast([user for user in channel.users], 'NOTICE {} :{}'.format(channel.name, msg))
                    client.idle = int(time.time())

                if s_sync:
                    self.ircd.new_sync(self.ircd, sourceServer, ':{} NOTICE {} :{}'.format(sourceID, target, msg))
                else:
                    logging.debug('Not syncing because s_sync: {}'.format(msg))

                if type(client).__name__ == 'User':
                    for callable in [callable for callable in self.ircd.hooks if callable[0].lower() == 'channotice']:
                        try:
                            callable[2](client, self.ircd, channel, msg)
                        except Exception as ex:
                            logging.exception(ex)
