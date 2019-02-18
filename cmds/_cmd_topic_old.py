import time
import os
import sys
from handle.functions import checkSpamfilter, _print

def cmd_TOPIC(self, localServer, recv, override=False):
    try:
        ############################################################################################
        ### This should be at the start of every command, that requires syncing between servers. ###
        ############################################################################################
        if type(self).__name__ == 'Server':
            override = True
            originServer = self
            self = list(filter(lambda u: u.uid == recv[0][1:], localServer.users))
            if not self:
                self = list(filter(lambda s: s.sid == recv[0][1:], localServer.servers))
                if not self:
                    return
                else:
                    self = self[0]
                    sourceID = self.sid
            else:
                self = self[0]
                sourceID = self.uid
            ### Cut the recv to match original syntax. (there's now an extra :UID at the beginning.
            recv = localServer.parse_command(' '.join(recv[1:]))
        else:
            originServer = self.server
            sourceID = self.uid

        oper_override = False

        if len(recv) < 2:
            self.sendraw(461, ':TOPIC Not enough parameters')
            return

        channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), localServer.channels))
        if not channel:
            self.sendraw(401, '{} :No such channel'.format(recv[1]))
            return
        channel = channel[0]

        if len(recv) < 3:
            if not channel.topic:
                self.sendraw(331, '{} :No topic is set.'.format(channel.name))
                return

            self.sendraw(332, '{} :{}'.format(channel.name, channel.topic))
            self.sendraw(333, '{} {} {}'.format(channel.name, channel.topic_author, channel.topic_time))
        else:
            if not override:
                if self not in channel.users and not self.ocheck('o', 'override') and not override:
                    self.sendraw(442, '{} :You\'re not on that channel'.format(channel.name))
                    return
                elif self not in channel.users:
                    oper_override = True

                if 't' in channel.modes and self.chlevel(channel) < 2 and not self.ocheck('o', 'override') and not override:
                    self.sendraw(482, '{} :You\'re not a channel operator'.format(channel.name))
                    return
                elif 't' in channel.modes and self.chlevel(channel) < 2:
                    oper_override = True

            if type(self).__name__ == 'Server' or self.server != localServer:
                ### Help prevent endless topic loop between servers. Special snowflake fix.
                ### Not necessary anymore but leaving this here, there's no need to flood the topic anyway.
                if int(recv[3]) == channel.topic_time or channel.topic == recv[4][:localServer.topiclen]:
                    return
                if not override:
                    channel.topic = recv[4][:localServer.topiclen]
                else:
                    channel.topic = recv[4]
                channel.topic_author = recv[2]
                channel.topic_time = int(recv[3])
            else:
                if int(time.time()) <= channel.topic_time or channel.topic == recv[2]:
                    return
                if not override:
                    channel.topic = recv[2][:localServer.topiclen]
                else:
                    channel.topic = recv[2]
                channel.topic_author = self.fullmask()
                channel.topic_time = int(time.time())

            if checkSpamfilter(self, localServer, channel.name, 'topic', channel.topic):
                return
            if oper_override:
                localServer.snotice('s', '*** OperOverride by {} ({}@{}) with TOPIC {} {}'.format(self.nickname, self.ident, self.hostname, channel.name, channel.topic))

            self.broadcast(channel.users, 'TOPIC {} :{}'.format(channel.name, channel.topic))

            if channel.name[0] != '&':
                data = ':{} TOPIC {} {} {} :{}'.format(sourceID, channel.name, channel.topic_author, channel.topic_time, channel.topic)
                localServer.syncToServers(localServer, originServer, data)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e)
