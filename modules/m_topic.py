"""
/topic command
"""

import ircd

import time
from handle.functions import checkSpamfilter, logging, save_db

TOPICLEN = 350


@ircd.Modules.command
class Topic(ircd.Command):
    def __init__(self):
        self.command = 'topic'
        self.params = 1
        self.support = [('TOPICLEN', str(TOPICLEN)),]

    def execute(self, client, recv, override=0):
        text = None
        try:
            if type(client).__name__ == 'Server':
                override = True
                sourceServer = client
                S = recv[0][1:]
                source = [s for s in self.ircd.servers+[self.ircd] if s.sid == S or s.hostname == S]+[u for u in self.ircd.users if u.uid == S or u.nickname == S]
                source = source[0]
                if type(source).__name__ == 'User':
                    sourceID = source.uid
                else:
                    sourceID = source.sid
                recv = self.ircd.parse_command(' '.join(recv[1:]))
                if len(recv) < 5:
                    text = ''
                else:
                    text = recv[4]
            else:
                sourceServer = client.server
                sourceID = client.uid
                source = client

            oper_override = False

            channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), self.ircd.channels))
            if not channel:
                client.sendraw(401, '{} :No such channel'.format(recv[1]))
                return
            channel = channel[0]
            if len(recv) < 3:
                if not channel.topic:
                    return client.sendraw(331, '{} :No topic is set.'.format(channel.name))

                client.sendraw(332, '{} :{}'.format(channel.name, channel.topic))
                client.sendraw(333, '{} {} {}'.format(channel.name, channel.topic_author, channel.topic_time))
            else:
                if recv[2] == ':' and len(recv) < 4:
                    text = ''
                if type(client).__name__ == 'User':
                    recv = client.parse_command(' '.join(recv))
                if len(recv) > 2 or text is not None:
                    if text is None:
                        text = recv[2] if recv[2].startswith(':') else ' '.join(recv[2:])
                    if not override:
                        if client not in channel.users and not client.ocheck('o', 'override') and not override:
                            return client.sendraw(442, '{} :You\'re not on that channel'.format(channel.name))

                        elif client not in channel.users:
                            oper_override = True

                        if 't' in channel.modes and client.chlevel(channel) < 2 and not client.ocheck('o', 'override') and not override:
                            return client.sendraw(482, '{} :You\'re not a channel operator'.format(channel.name))

                        elif 't' in channel.modes and client.chlevel(channel) < 2:
                            oper_override = True
                    if type(client).__name__ == 'Server' or client.server != self.ircd:
                        if int(recv[3]) == channel.topic_time or channel.topic == text[:TOPICLEN]:
                            return
                        if not override:
                            channel.topic = text[:TOPICLEN]
                        else:
                            channel.topic = text
                        channel.topic_author = recv[2]
                        channel.topic_time = int(recv[3])
                    else:
                        if channel.topic and int(time.time()) <= channel.topic_time or channel.topic == text:
                            return
                        if not override:
                            channel.topic = text[:TOPICLEN]
                        else:
                            channel.topic = text
                        channel.topic_author = client.fullmask()
                        channel.topic_time = int(time.time())

                if not override and checkSpamfilter(client, self.ircd, channel.name, 'topic', channel.topic):
                    return
                if oper_override:
                    self.ircd.snotice('s', '*** OperOverride by {} ({}@{}) with TOPIC {} \'{}\''.format(client.nickname, client.ident, client.hostname, channel.name, channel.topic))

                source.broadcast(channel.users, 'TOPIC {} :{}'.format(channel.name, channel.topic))

                if channel.name[0] != '&':
                    data = ':{} TOPIC {} {} {} :{}'.format(sourceID, channel.name, channel.topic_author, channel.topic_time, channel.topic)
                    self.ircd.new_sync(self.ircd, sourceServer, data)
                save_data(self.ircd)

        except Exception as ex:
            logging.exception(ex)
