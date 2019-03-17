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

from handle.functions import _print

parts_showed = {}
joins_showed = {}

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes(chmode, 3, 3, 'Delay join message until the user speaks or receives channel status') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.hooks.pre_chanmsg()
def showjoin(self, localServer, channel, msg):
    if 'D' not in channel.modes:
        return msg
    if self in channel.delayjoins:
        channel.delayjoins.remove(self)
        broadcast = [user for user in channel.users if user not in joins_showed[channel][self] and user != self]
        self.broadcast(broadcast, 'JOIN :{}'.format(channel.name))
        for user in broadcast:
            joins_showed[channel][self][user] = True
            if user in parts_showed[channel][self]:
                del parts_showed[channel][self][user]
    return msg

@ircd.Modules.hooks.visible_in_channel() ### Returns True or False depending if <user> should be visible on <channel>
def visible_in_chan(self, localServer, user, channel):
    if chmode in channel.modes and user in channel.delayjoins and self not in joins_showed[channel][user]:
        if self.chlevel(channel) < 2:
            return 0
    return 1

@ircd.Modules.hooks.pre_local_join()
def hidejoin(self, localServer, channel):
    ### NoneType issues? Always make sure to return a tuple!
    overrides = []
    try:
        if 'D' not in channel.modes:
            return (True, None, overrides)
        if self not in parts_showed[channel]:
            parts_showed[channel][self] = {}
        if self not in joins_showed[channel]:
            joins_showed[channel][self] = {}
        if not hasattr(channel, 'delayjoins'):
            channel.delayjoins = []
        if self not in channel.delayjoins:
            channel.delayjoins.append(self)
        broadcast = [user for user in channel.users if user.chlevel(channel) > 1]+[self]
        for user in broadcast:
            joins_showed[channel][self][user] = True
        return (True, broadcast, overrides) ### Bool 1: is the join allowed? Param 2: list of users to broadcast the join to.

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

@ircd.Modules.hooks.pre_local_part()
def hidepart(self, localServer, channel):
    if 'D' not in channel.modes:
        return (True, None)
    try:
        all_part = False
        if self not in joins_showed[channel]:
            joins_showed[channel][self] = {}
            ### Show part to everyone.
            all_part = True
        if self not in parts_showed[channel]:
            parts_showed[channel][self] = {}

        #broadcast = [user for user in channel.users if all_part or user in joins_showed[channel][self] and (self in parts_showed[channel] and user not in parts_showed[channel][self])]
        broadcast = [user for user in channel.users if all_part or user in joins_showed[channel][self]]
        for user in broadcast:
            parts_showed[channel][self][user] = True
            if user in joins_showed[channel][self]:
                del joins_showed[channel][self][user]
        if self in channel.delayjoins:
            channel.delayjoins.remove(self)
        return (True, broadcast)
    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

@ircd.Modules.hooks.pre_local_quit()
def hidequit(self, localServer):
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
        _print(e, server=localServer)

@ircd.Modules.hooks.modechar_add()
def set_D(channel, mode):
    if mode == chmode:
        if channel not in joins_showed:
            joins_showed[channel] = {}
        if channel not in parts_showed:
            parts_showed[channel] = {}

@ircd.Modules.hooks.modechar_del()
def unset_D(channel, mode):
    if mode == chmode:
        for delayed_user in [delayed_user for delayed_user in channel.users if delayed_user in list(channel.delayjoins)]:
            show_joins(delayed_user, channel)
            channel.delayjoins.remove(delayed_user)

@ircd.Modules.hooks.pre_local_chanmode()
@ircd.Modules.hooks.pre_remote_chanmode()
def chmode_D(self, localServer, channel, modes, params, modebuf, parambuf, paramcount=0):
    try:
        if not hasattr(channel, 'delayjoins') or not channel.delayjoins:
            channel.delayjoins = []
        #paramcount = 0
        action = ''
        for m in modebuf:
            if m in '+-':
                action = m
                continue

            if action in '+-' and chmode in channel.modes and m in localServer.chstatus:
                try:
                    p = parambuf[paramcount].split(':')[0]
                except IndexError:
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
                    for delayed_user in list(channel.delayjoins):
                        if delayed_user == user:
                            show_joins(delayed_user, channel)
                            channel.delayjoins.remove(delayed_user)
                            continue
                        if user.chlevel(channel) >= 2:
                            show_joins(delayed_user, channel, user)

    except Exception as ex:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        e = 'EXCEPTION: {} in file {} line {}: {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno, exc_obj)
        _print(e, server=localServer)

def show_joins(delayed_user, channel, user=None):
    if delayed_user not in joins_showed[channel]:
        joins_showed[channel][delayed_user] = {}
    users = [user for user in channel.users if user not in joins_showed[channel][delayed_user] and user != delayed_user] if not user else [user]
    for user in [user for user in users if user not in joins_showed[channel][delayed_user]]:
        joins_showed[channel][delayed_user][user] = True
        delayed_user.broadcast([user], 'JOIN :{}'.format(channel.name))
        if user in parts_showed[channel][delayed_user]:
            del parts_showed[channel][delayed_user][user]

def show_parts(delayed_user, channel):
    if delayed_user not in parts_showed[channel]:
        parts_showed[channel][delayed_user] = {}
    for user in [user for user in channel.users if user not in parts_showed[channel][delayed_user] and user.chlevel(channel) < 2 and user != delayed_user]:
        parts_showed[channel][delayed_user][user] = True
        delayed_user.broadcast([user], 'PART :{}'.format(channel.name))
        if user in joins_showed[channel][delayed_user]:
            del joins_showed[channel][delayed_user][user]

@ircd.Modules.hooks.pre_local_kick()
def kick(self, localServer, user, channel, reason):
    if chmode not in channel.modes:
        return True
    show_joins(user, channel)
    ### Because this is a kick event, we will delete it from joins_showed dict.
    if user in joins_showed[channel]:
        del joins_showed[channel][user]
    return True

def init(self):
    for chan in [chan for chan in self.channels if chmode in chan.modes]:
        joins_showed[chan] = {}
        parts_showed[chan] = {}

def unload(self):
    for channel in [channel for channel in self.channels if chmode in channel.modes]:
        if channel not in joins_showed:
            return
        for delayed_user in list(channel.delayjoins):
            show_joins(delayed_user, channel)
            channel.delayjoins.remove(delayed_user)
