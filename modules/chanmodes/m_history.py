"""
provides chmode +H (backlog support)
"""

import time
from datetime import datetime

import ircd
from handle.functions import logging

chmode = 'H'


class chmode_H(ircd.ChannelMode):
    def __init__(self):
        self.mode = chmode
        self.desc = 'Displays the message backlog to new users'
        self.type = 2
        self.level = 4
        self.param_format = "<int>:<int>"
        self.param_help = '[maxlines:expire_in_minutes]'


@ircd.Modules.hooks.loop()
def checkExpiredBacklog(localServer):
    for chan in [channel for channel in localServer.channels if chmode in channel.modes and hasattr(channel, 'msg_backlog') and channel.msg_backlog['lines']]:
        latest_date = chan.msg_backlog['lines'][-1][1] / 10
        expire = chan.msg_backlog['expire'] * 60
        if float(datetime.utcnow().strftime("%s.%f")) - latest_date > expire:
            chan.msg_backlog['lines'] = []  # Remove all lines.


ircd.Modules.hooks.channel_destroy()


def destroy(self, localServer, channel):
    if chmode in channel.modes:
        channel.backlog = {}


@ircd.Modules.hooks.chanmsg()
def history_msg(self, localServer, channel, msg):
    try:
        if chmode not in channel.modes:
            return
        limit = channel.msg_backlog['limit']  # Max lines to remember.
        expire = channel.msg_backlog['expire'] * 60
        while len(channel.msg_backlog['lines']) >= limit:
            channel.msg_backlog['lines'] = channel.msg_backlog['lines'][1:]
        utc_time = float(datetime.utcnow().strftime("%s.%f")) * 10
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

        for user in [user for user in list(localServer.m_history[channel]) if user not in channel.users]:
            del localServer.m_history[channel][user]
    except Exception as ex:
        logging.exception(ex)


@ircd.Modules.hooks.pre_local_chanmode(chmode)
@ircd.Modules.hooks.pre_remote_chanmode(chmode)
def chmode_H2(self, localServer, channel, modebuf, parambuf, action, modebar, param):
    try:
        if action == '+':
            limit = int(param.split(':')[0])
            if limit > 25:
                limit = 25
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
            # modebuf.append(modebar)
            # parambuf.append(param)
            # channel.modes += modebar
            # Actually we should also add the chan_param here. BUT MEH FUCK IT.
            # return 0
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
            if localServer.m_history[channel][self]['last'] != channel.msg_backlog['lines'][-1] or int(time.time()) - localServer.m_history[channel][self]['replay_time'] > 1800:
                ### New messages for user.
                show = 1
        else:
            show = 1
        if show:
            self._send(':{} PRIVMSG {} :Displaying backlog for {}'.format(localServer.hostname, channel.name, channel.name))
            for entry in channel.msg_backlog['lines']:
                prefix = ''
                timestamp = int(entry[1] / 10)
                if 'server-time' in self.caplist:
                    prefix = '@time={}.{}Z '.format(time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(timestamp)), round(entry[1] % 1000))
                data = '{}:{} PRIVMSG {} :{}'.format(prefix, entry[0], channel.name, entry[2])
                self._send(data)
            self._send(':{} PRIVMSG {} :Done displaying last {} messages.'.format(localServer.hostname, channel.name, len(channel.msg_backlog['lines'])))
            localServer.m_history[channel][self]['replay_time'] = int(time.time())
            localServer.m_history[channel][self]['last'] = channel.msg_backlog['lines'][-1]


@ircd.Modules.hooks.local_quit()
def clear_info(ircd, self):
    for chan in [chan for chan in ircd.channels if chan in ircd.m_history and self in ircd.m_history[chan]]:
        del ircd.m_history[chan][self]


def init(ircd, reload=False):
    ircd.m_history = {}
