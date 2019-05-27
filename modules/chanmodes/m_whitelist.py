#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
provides chmode +w (white list)
"""

import ircd
import time
import os
import sys
import re
from handle.functions import logging, match
from modules.m_mode import makeMask
from collections import OrderedDict

chmode = 'w'
info = """Help is coming soon."""
helpop = {"whitelist": info}

@ircd.Modules.hooks.local_join()
def join(self, localServer, channel):
    if not hasattr(channel, 'whitelist'):
        channel.whitelist = {}
    last_level = 0
    total_modes, total_params = '+', ''
    for entry in channel.whitelist:
        level = int(entry.split(':')[0])
        if level > last_level:
            ### Found higher level.
            last_level = level
        mask = entry.split(':')[1]
        modes = ''
        if match(mask, self.fullmask()):
            if level >= 9999:
                modes += 'oq'
            elif level >= 10:
                modes += 'oa'
            elif level >= 5:
                modes += 'o'
            elif level >= 4:
                modes += 'h'
            elif level >= 1:
                modes += 'v'
        if modes:
            nicks = '{} '.format(self.nickname) * len(modes)
            total_modes += modes
            total_params += nicks
    if total_modes and total_params:
        localServer.handle('MODE', '{} {} {}'.format(channel.name, total_modes, total_params))

### Types: 0 = mask, 1 = require param, 2 = optional param, 3 = no param, 4 = special user channel-mode.
@ircd.Modules.channel_modes(chmode, 0, 5, 'Maintain a "whitelist" for your channel (/helpop whitelist for more info)', None, None, '<level>:<nick!ident@host>') ### ('mode', type, level, 'Mode description', class 'user' or None, prefix, 'param desc')
@ircd.Modules.hooks.pre_local_chanmode()
@ircd.Modules.hooks.pre_remote_chanmode()
def whitelist_mode(self, localServer, channel, modebuf, parambuf, action, m, param):
    if m != chmode:
        return
    try:
        if (action == '+' or not action) and not param:
            ### Requesting list.
            if self.chlevel(channel) < 3 and not self.ocheck('o', 'override'):
                return self.sendraw(482, '{} :You are not allowed to view the whitelist'.format(channel.name))
            for entry in OrderedDict(reversed(list(channel.whitelist.items()))):
                self.sendraw(348, '{} {} {} {}'.format(channel.name, entry, channel.whitelist[entry]['setter'], channel.whitelist[entry]['ctime']))
            return self.sendraw(349, '{} :End of Channel Whitelist'.format(channel.name))

        valid = re.findall("^([1-9][0-9]{0,3}):(.*)", param)
        if not valid:
           return logging.info('Invalid param for {}{}: {}'.format(action, m, param))

        mask = makeMask(localServer, param.split(':')[1])
        logging.info('Param for {}{} set: {}'.format(action, m, param))
        logging.info('Mask: {}'.format(mask))
        raw_param = param
        param = '{}:{}'.format(':'.join(param.split(':')[:1]), mask)
        if action == '+':
            if param in channel.whitelist:
                return
            try:
                setter = self.fullmask()
            except:
                setter = self.hostname
            channel.whitelist[param] = {}
            channel.whitelist[param]['setter'] = setter
            channel.whitelist[param]['ctime'] = int(time.time())
            #modebuf.append(m)
            parambuf.append(param)
        elif action == '-' and (param in channel.whitelist or raw_param in channel.whitelist):
            if param in channel.whitelist:
                del channel.whitelist[param]
                parambuf.append(param)
            else:
                del channel.whitelist[raw_param]
                parambuf.append(raw_param)
        modebuf.append(m)

    except Exception as ex:
        logging.exception(ex)

def init(localServer, reload=False):
    for chan in [chan for chan in localServer.channels if not hasattr(chan, 'whitelist')]:
        chan.whitelist = {}
