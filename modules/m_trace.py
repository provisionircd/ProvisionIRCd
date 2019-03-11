#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
extbans ~country and ~isp
"""

import ircd
import json
import requests
import logging
import time
from modules.chanmodes.m_extbans import prefix, ext_bans
trace_bans = ['country', 'isp']
for e in trace_bans:
    if e in ext_bans:
        logging.error('Unable to load m_trace: conflicting with existing extban')

@ircd.Modules.hooks.local_connect()
def connect_hook(self, localServer):
    if not hasattr(self, 'geodata'):
        url = 'https://extreme-ip-lookup.com/json/'+self.ip
        response = requests.get(url)
        json_res = response.json()
        self.geodata = json_res

@ircd.Modules.hooks.pre_local_chanmode()
@ircd.Modules.hooks.pre_remote_chanmode()
def extbans(self, localServer, channel, modes, params, modebuf, parambuf, paramcount=0):
    try:
        action = ''
        for m in modes:
            if m in '+-':
                action = m
                continue
            try:
                rawParam = params[paramcount]
            except:
                paramcount += 1
                continue
            try:
                rawParam.split(':')[1][0]
            except:
                paramcount += 1
                continue
            if rawParam[0] != prefix:
                paramcount += 1
                continue

            if rawParam.split(':')[0][1:] not in trace_bans:
                paramcount += 1
                continue
            try:
                setter = self.fullmask()
            except:
                setter = self.hostname

            c = None
            if m == 'b':
                c = channel.bans
            elif m == 'I':
                c = channel.invex
            elif m == 'e':
                c = channel.excepts
            if c is not None:
                paramcount += 1
                if action == '+' and rawParam not in c:
                    modebuf.append(m)
                    parambuf.append(rawParam)
                    c[rawParam] = {}
                    c[rawParam]['setter'] = setter
                    c[rawParam]['ctime'] = int(time.time())

    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.pre_local_join()
def join(self, localServer, channel):
    try:
        overrides = []
        invite_override = False
        if self in channel.invites:
            invite_override = channel.invites[self]['override']
        if hasattr(self, 'geodata'):
            for b in [b for b in channel.bans if b[:8] == '~country']: ### Country ban.
                banCountry = b.split(':')[1]
                if self.geodata['country'].lower() == banCountry.lower() or self.geodata['countryCode'].lower() == banCountry.lower() and not checkMatch(self, localServer, 'e', channel) and not invite_override:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, None, overrides)
            for b in [b for b in channel.bans if b[:4] == '~isp']: ### ISP ban.
                banISP = b.split(':')[1]
                if self.geodata['isp'].lower() == banISP.lower() and not checkMatch(self, localServer, 'e', channel) and not invite_override:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, None, overrides)

            for i in channel.invex:
                if i.startswith('~country'):
                    country = i.split(':')[1].lower()
                    if 'i' in channel.modes and (self.geodata['country'].lower() == country or self.geodata['countryCode'].lower() == country) and 'i' not in overrides:
                        overrides.append('i')

                if i.startswith('~isp'):
                    isp = i.split(':')[1].lower()
                    if 'i' in channel.modes and self.geodata['isp'].lower() == isp and 'i' not in overrides:
                        overrides.append('i')

        return (True, None, overrides)

    except Exception as ex:
        logging.exception(ex)
