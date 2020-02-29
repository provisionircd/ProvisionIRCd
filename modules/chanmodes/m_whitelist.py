"""
provides chmode +w (white list)
"""

import ircd
import time
import os
import sys
import re
from handle.functions import logging, match, make_mask
from collections import OrderedDict

chmode = 'w'

class Chmode_w(ircd.ChannelMode):
    def __init__(self):
        self.mode = chmode
        self.type = 0 # +beI family
        self.level = 5
        self.desc = 'Maintain a "whitelist" for your channel (/helpop whitelist for more info)'
        self.param_help = '<level>:<nick!ident@host>'
        self.mode_prefix = '^' ### This is used in SJOIN to indicate that it is a whitelist-entry.
        self.list_name = 'whitelist'


info = """
Add or remove entries to your channel "whitelist",
allowing users to automatically get a status on join based on nick!ident@host matches.
Syntax:     +w <level>:<host>
-
Example:    +w 5:*!*@*.trusted.host --- will give +o to anyone joining whose host matches *!*@*.trusted.host
Levels:     >=1     = +v
            >=4     = +h
            >=5     = +o
            >= 10   = +ao
            >= 9999 = +oq
"""
helpop = {"whitelist": info}


@ircd.Modules.hooks.local_join()
def join(self, ircd, channel):
    mod = next((m for m in ircd.channel_mode_class if m.mode == chmode), None)
    if not mod:
        logging.error(f"Module for channele mode '{chmode}' not found.")
        return
    if not hasattr(channel, mod.list_name):
        setattr(channel, mod.list_name, {})

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
        ircd.handle('MODE', '{} {} {}'.format(channel.name, total_modes, total_params))



@ircd.Modules.hooks.pre_remote_chanmode('w')
@ircd.Modules.hooks.pre_local_chanmode('w')
def whitelist_mode(self, localServer, channel, modebuf, parambuf, action, modebar, param):
    try:
        if (action == '+' or not action) and not param:
            ### Requesting list.
            if self.chlevel(channel) < 3 and 'o' not in self.modes:
                return self.sendraw(482, '{} :You are not allowed to view the whitelist'.format(channel.name))
            for entry in OrderedDict(reversed(list(channel.whitelist.items()))):
                self.sendraw(348, '{} {} {} {}'.format(channel.name, entry, channel.whitelist[entry]['setter'], channel.whitelist[entry]['ctime']))
            self.sendraw(349, '{} :End of Channel Whitelist'.format(channel.name))
            return 0
        elif not param:
            return
        valid = re.findall("^([1-9][0-9]{0,3}):(.*)", param)
        if not valid:
           logging.info('Invalid param for {}{}: {}'.format(action, modebar, param))
           return 0

        mask = make_mask(localServer, param.split(':')[1])
        logging.info('Param for {}{} set: {}'.format(action, modebar, param))
        logging.info('Mask: {}'.format(mask))
        raw_param = param
        param = '{}:{}'.format(':'.join(param.split(':')[:1]), mask)
        if action == '+':
            if param in channel.whitelist:
                return 0
            try:
                setter = self.fullmask()
            except Exception as ex:
                setter = self.hostname
            channel.whitelist[param] = {}
            channel.whitelist[param]['setter'] = setter
            channel.whitelist[param]['ctime'] = int(time.time())
            modebuf.append(modebar)
            parambuf.append(param)

        elif action == '-' and (param in channel.whitelist or raw_param in channel.whitelist):
            if param in channel.whitelist:
                del channel.whitelist[param]
                parambuf.append(param)
            else:
                del channel.whitelist[raw_param]
                parambuf.append(raw_param)

            modebuf.append(modebar)

        return 0

    except Exception as ex:
        logging.exception(ex)



@ircd.Modules.hooks.channel_destroy()
def destroy(self, ircd, channel):
    mod = next((m for m in ircd.channel_mode_class if m.mode == chmode), None)
    if not mod:
        logging.error(f"Module for channele mode '{chmode}' not found.")
        return
    setattr(channel, mod.list_name, {})


def init(ircd, reload=False):
    mod = next((m for m in ircd.channel_mode_class if m.mode == chmode), None)
    if not mod:
        logging.error(f"Module for channele mode '{chmode}' not found.")
        return
    for chan in [chan for chan in ircd.channels if not hasattr(chan, mod.list_name)]:
        setattr(chan, mod.list_name, {})
