"""
provides chmode +H (backlog support)
"""

import ircd
import re
import os
import sys
import time
from datetime import datetime

from handle.functions import logging

chmode = 'H'

@ircd.Modules.hooks.loop()
def checkExpiredBacklog(localServer):
    for chan in [channel for channel in localServer.channels if chmode in channel.modes and channel.msg_backlog['lines']]:
        latest_date = chan.msg_backlog['lines'][-1][1]/10
        expire = chan.msg_backlog['expire'] * 60
        if float(datetime.utcnow().strftime("%s.%f")) - latest_date > expire:
            #localServer.handle('PRIVMSG', '{} :Message expired: {}'.format(chan.name, line))
            chan.msg_backlog['lines'] = [] # Remove all lines.
            #chan.msg_backlog['lines'] = chan.msg_backlog['lines'][1:] # Remove only expired line.
    #for user in [user for user in localServer.m_history if int(time.time()) - localServer.m_history[user]['replayed_time'] > 60]:
    #    pass

ircd.Modules.hooks.channel_destroy()
def destroy(self, localServer, channel):
    if chmode in channel.modes:
        channel.backlog = {}

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param
@ircd.Modules.channel_modes(chmode, 2, 5, 'Displays the message backlog to new users', None, None, '[maxlines:expire_in_minutes]') ### ('mode', type, level, 'Mode description')
@ircd.Modules.hooks.chanmsg()
def history_msg(self, localServer, channel, msg):
    try:
        if chmode not in channel.modes:
            return
        limit = channel.msg_backlog['limit'] # Max lines to remember.
        expire = channel.msg_backlog['expire'] * 60
        while len(channel.msg_backlog['lines']) >= limit:
            channel.msg_backlog['lines'] = channel.msg_backlog['lines'][1:]
        utc_time = float(datetime.utcnow().strftime("%s.%f"))*10
        data = (self.fullmask(), utc_time, msg)
        if channel.msg_backlog['lines']:
            channel.msg_backlog['previous_last'] = channel.msg_backlog['lines'][-1]
        channel.msg_backlog['lines'].append(data)
        if channel not in localServer.m_history:
            localServer.m_history[channel] = {}
        for user in channel.users:
            if user not in localServer.m_history[channel]:
                localServer.m_history[channel][user] = {}
                localServer.m_history[channel][user]['last'] = None
                localServer.m_history[channel][user]['replay_time'] = int(time.time())
            localServer.m_history[channel][user]['last'] = data
        ### Looking for parted users.
        for user in [user for user in list(localServer.m_history[channel]) if user not in channel.users]:
            del localServer.m_history[channel][user]
    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.pre_local_chanmode()
@ircd.Modules.hooks.pre_remote_chanmode()
def chmode_H(self, localServer, channel, modebuf, parambuf, action, m, param):
    try:
        if m == chmode:
            if action == '+':
                if not re.findall("(.):(.)", param) or not param.split(':')[0].isdigit() or not param.split(':')[1].isdigit():
                    logging.info('Param {} is invalid for {}{}'.format(param, action, m))
                    return
                limit = int(param.split(':')[0])
                if limit > 50:
                    limit = 50
                expire = int(param.split(':')[1])
                if expire > 10080:
                    expire = 10080
                param = '{}:{}'.format(limit, expire)
                if not hasattr(channel, 'msg_backlog'):
                    channel.msg_backlog = {}
                elif 'lines' in channel.msg_backlog:
                    if limit == channel.msg_backlog['limit'] and expire == channel.msg_backlog['expire']:
                        return
                channel.msg_backlog['limit'] = limit
                channel.msg_backlog['expire'] = expire
                channel.msg_backlog['lines'] = []
                modebuf.append(m)
                parambuf.append(param)
                channel.modes += m
            else:
                channel.msg_backlog = {}
    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.local_join()
def show_history(self, localServer, channel):
    if chmode in channel.modes and channel.msg_backlog['lines']:
        show = 0
        if channel not in localServer.m_history:
            localServer.m_history[channel] = {}
        if self not in localServer.m_history[channel]:
            localServer.m_history[channel][self] = {}
            localServer.m_history[channel][self]['last'] = None
            localServer.m_history[channel][self]['replay_time'] = int(time.time())
        if 'replay_time' in localServer.m_history[channel][self] and 'last' in localServer.m_history[channel][self]:
            if localServer.m_history[channel][self]['last'] != channel.msg_backlog['lines'][-1] or int(time.time()) - localServer.m_history[channel][self]['replay_time'] > 600:
                ### New messages for user.
                show = 1
        else:
            show = 1
        if show:
            self._send(':{} PRIVMSG {} :Displaying backlog for {}'.format(localServer.hostname, channel.name, channel.name))
            for entry in channel.msg_backlog['lines']:
                prefix = ''
                timestamp = int(entry[1]/10)
                if 'server-time' in self.caplist:
                    prefix = '@time={}.{}Z '.format(time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(timestamp)), round(entry[1]%1000))
                data = '{}:{} PRIVMSG {} :{}'.format(prefix, entry[0], channel.name, entry[2])
                self._send(data)
            self._send(':{} PRIVMSG {} :Done displaying last {} messages.'.format(localServer.hostname, channel.name, len(channel.msg_backlog['lines'])))
            localServer.m_history[channel][self]['replay_time'] = int(time.time())
            localServer.m_history[channel][self]['last'] = channel.msg_backlog['lines'][-1]

def init(self, reload):
    self.m_history = {}
