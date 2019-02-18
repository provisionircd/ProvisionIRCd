#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
/topic command
"""

import ircd

import time
import os
import sys
from handle.functions import checkSpamfilter, _print

topiclen = 307

@ircd.Modules.params(1)
@ircd.Modules.support('TOPICLEN='+str(topiclen))
@ircd.Modules.commands('topic')
def topic(self, localServer, recv, override=False):
    text = None
    try:
        if type(self).__name__ == 'Server':
            override = True
            sourceServer = self
            S = recv[0][1:]
            source = [s for s in localServer.servers+[localServer] if s.sid == S or s.hostname == S]+[u for u in localServer.users if u.uid == S or u.nickname == S]
            source = source[0]
            if type(source).__name__ == 'User':
                sourceID = source.uid
            else:
                sourceID = source.sid
            recv = localServer.parse_command(' '.join(recv[1:]))
            if len(recv) < 5:
                text = ''
            else:
                text = recv[4]
        else:
            sourceServer = self.server
            sourceID = self.uid
            source = self

        oper_override = False

        channel = list(filter(lambda c: c.name.lower() == recv[1].lower(), localServer.channels))
        if not channel:
            self.sendraw(401, '{} :No such channel'.format(recv[1]))
            return
        channel = channel[0]
        if len(recv) < 3:
            if not channel.topic:
                return self.sendraw(331, '{} :No topic is set.'.format(channel.name))

            self.sendraw(332, '{} :{}'.format(channel.name, channel.topic))
            self.sendraw(333, '{} {} {}'.format(channel.name, channel.topic_author, channel.topic_time))
        else:
            if recv[2] == ':':
                text = ''
            if type(self).__name__ == 'User':
                recv = self.parse_command(' '.join(recv))
            if len(recv) > 2 or text is not None:
                if text is None:
                    text = recv[2] if recv[2].startswith(':') else ' '.join(recv[2:])
                if not override:
                    if self not in channel.users and not self.ocheck('o', 'override') and not override:
                        return self.sendraw(442, '{} :You\'re not on that channel'.format(channel.name))

                    elif self not in channel.users:
                        oper_override = True

                    if 't' in channel.modes and self.chlevel(channel) < 2 and not self.ocheck('o', 'override') and not override:
                        return self.sendraw(482, '{} :You\'re not a channel operator'.format(channel.name))

                    elif 't' in channel.modes and self.chlevel(channel) < 2:
                        oper_override = True
                if type(self).__name__ == 'Server' or self.server != localServer:
                    if int(recv[3]) == channel.topic_time or channel.topic == text[:topiclen]:
                        return
                    if not override:
                        channel.topic = text[:topiclen]
                    else:
                        channel.topic = text
                    channel.topic_author = recv[2]
                    channel.topic_time = int(recv[3])
                else:
                    if channel.topic and int(time.time()) <= channel.topic_time or channel.topic == text:
                        return
                    if not override:
                        channel.topic = text[:topiclen]
                    else:
                        channel.topic = text
                    channel.topic_author = self.fullmask()
                    channel.topic_time = int(time.time())

            if not override and checkSpamfilter(self, localServer, channel.name, 'topic', channel.topic):
                return
            if oper_override:
                localServer.snotice('s', '*** OperOverride by {} ({}@{}) with TOPIC {} \'{}\''.format(self.nickname, self.ident, self.hostname, channel.name, channel.topic))

            source.broadcast(channel.users, 'TOPIC {} :{}'.format(channel.name, channel.topic))

            if channel.name[0] != '&':
                data = ':{} TOPIC {} {} {} :{}'.format(sourceID, channel.name, channel.topic_author, channel.topic_time, channel.topic)
                localServer.new_sync(localServer, sourceServer, data)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)
