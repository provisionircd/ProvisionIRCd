#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides chmode +D (delay join)
"""

import ircd
import threading
import os
import sys

chmode = 'D'

parts_showed = {}
joins_showed = {}

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes(chmode, 3, 3, 'Delay join message until the user speaks') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.events('privmsg')
def showjoin(self, localServer, channel, msg, module):
    if 'D' not in channel.modes:
        return True
    if self in channel.delayjoins:
        channel.delayjoins.remove(self)
        broadcast = [user for user in channel.users if user not in joins_showed[channel][self] and user != self]
        self.broadcast(broadcast, 'JOIN :{}'.format(channel.name))
        for user in broadcast:
            joins_showed[channel][self][user] = True
    return True

@ircd.Modules.events('join')
def hidejoin(self, localServer, channel):
    ### NoneType issues? Always make sure to return a tuple!
    overrides = []
    try:
        if 'D' not in channel.modes:
            return (True, None, overrides)
        if self not in joins_showed[channel]:
            joins_showed[channel][self] = {}
        if self not in parts_showed[channel]:
            parts_showed[channel][self] = {}
        if not hasattr(channel, 'delayjoins'):
            channel.delayjoins = []
        if self not in channel.delayjoins:
            channel.delayjoins.append(self)
        broadcast = [user for user in channel.users if user.chlevel(channel) > 1]+[self]
        for user in broadcast:
            joins_showed[channel][self][user] = True
        print('returning {}'.format(broadcast))
        return (True, broadcast, overrides) ### Bool 1: is the join allowed? Param 2: list of users to broadcast the join to.

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        print(e)

@ircd.Modules.events('part')
def hidepart(self, localServer, channel):
    if 'D' not in channel.modes:
        return (True, None)
    try:
        broadcast = [user for user in channel.users if user in joins_showed[channel][self] and user not in parts_showed[channel][self]]
        for user in broadcast:
            parts_showed[channel][self][user] = True
            del joins_showed[channel][self][user]
        if self in channel.delayjoins:
            channel.delayjoins.remove(self)
        return (True, broadcast)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        print(e)

@ircd.Modules.events('quit')
def hidequit(self, localServer, reason):
    try:
        broadcast = None
        for channel in [channel for channel in self.channels if 'D' in channel.modes]:
            if not broadcast:
                broadcast = []
            for user in [user for user in channel.users if user in joins_showed[channel][self] and user not in parts_showed[channel][self] and user != self and user not in broadcast]:
                broadcast.append(user)
            if hasattr(channel, 'delayjoins') and self in list(channel.delayjoins):
                channel.delayjoins.remove(self)
                continue
        return (True, broadcast)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        print(e)

@ircd.Modules.events('mode')
def unsetmode(*args):
    try:
        self = args[0]
        localServer = args[1]
        recv = args[2]
        channel = list(filter(lambda c: c.name.lower() == recv[0].lower(), localServer.channels))
        if not channel:
            return
        channel = channel[0]
        if not hasattr(channel, 'delayjoins') or not channel.delayjoins:
            channel.delayjoins = []

        paramcount = 0
        action = ''
        for m in recv[1]:
            if m in '+-':
                action = m
                continue
            if action == '-' and m == 'D':
                for delayed_user in [delayed_user for delayed_user in channel.users if delayed_user in list(channel.delayjoins)]:
                    show_joins(delayed_user, channel)
                    channel.delayjoins.remove(delayed_user)
                    continue
            if action == '+' and m == 'D':
                if channel not in joins_showed:
                    joins_showed[channel] = {}
                if channel not in parts_showed:
                    parts_showed[channel] = {}
                continue

            if action in '+-' and 'D' in channel.modes and m in localServer.chstatus:
                try:
                    p = recv[2:][paramcount].split(':')[0]
                except Exception as ex:
                    paramcount += 1
                    continue

                user = list(filter(lambda u: u.uid == p or u.nickname.lower() == p.lower(), channel.users))
                if not user:
                    paramcount += 1
                    continue
                user = user[0]
                if action == '-':
                    for delayed_user in list(channel.delayjoins):
                        show_parts(delayed_user, channel)

                if action == '+':
                    ### if the delayed user gets any mode, show the join to all users.
                    for delayed_user in list(channel.delayjoins):
                        if delayed_user == user:
                            show_joins(delayed_user, channel)
                            channel.delayjoins.remove(delayed_user)
                            continue
                        if user.chlevel(channel) >= 2:
                            show_joins(delayed_user, channel, user)
            paramcount += 1

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        print(e)

def show_joins(delayed_user, channel, user=None):
    if delayed_user not in joins_showed[channel]:
        return
    users = [user for user in channel.users if user not in joins_showed[channel][delayed_user] and user != delayed_user] if not user else [user]
    for user in [user for user in users if user not in joins_showed[channel][delayed_user]]:
        joins_showed[channel][delayed_user][user] = True
        delayed_user.broadcast([user], 'JOIN :{}'.format(channel.name))
        if user in parts_showed[channel][delayed_user]:
            del parts_showed[channel][delayed_user][user]

def show_parts(delayed_user, channel):
    if delayed_user not in parts_showed[channel]:
        return
    for user in [user for user in channel.users if user not in parts_showed[channel][delayed_user] and user.chlevel(channel) < 2 and user != delayed_user]:
        parts_showed[channel][delayed_user][user] = True
        delayed_user.broadcast([user], 'PART :{}'.format(channel.name))
        if user in joins_showed[channel][delayed_user]:
            del joins_showed[channel][delayed_user][user]

@ircd.Modules.events('kick')
def kick(self, localServer, user, channel, reason):
    if 'D' not in channel.modes:
        return True
    show_joins(user, channel)
    ### Because this is a kick event, we will delete it from joins_showed dict.
    if user in joins_showed[channel]:
        del joins_showed[channel][user]
    return True

@ircd.Modules.events('names')
def names(self, localServer, channel):
    exclude = []
    if 'D' in channel.modes:
        for delayed_user in list(channel.delayjoins):
            if self.chlevel(channel) < 2 and delayed_user != self:
                exclude.append(delayed_user)
    return (True, exclude)

def init(self):
    for chan in [chan for chan in self.channels if 'D' in chan.modes]:
        joins_showed[chan] = {}
        parts_showed[chan] = {}

def unload(self):
    for channel in [channel for channel in self.channels if 'D' in channel.modes]:
        if channel not in joins_showed:
            return
        for delayed_user in list(channel.delayjoins):
            show_joins(delayed_user, channel)
            channel.delayjoins.remove(delayed_user)
