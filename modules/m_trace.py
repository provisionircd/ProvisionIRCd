#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
extbans ~C (country) and ~i (ISP), requires m_extbans to be loaded
"""

import ircd
import json
#import requests ### This module will increase the RAM usage by ~10MB. Ain't that a hoot.
import urllib.request
import logging
import time
import re
from modules.chanmodes.m_extbans import prefix, ext_bans
from modules.m_joinpart import checkMatch
from handle.functions import match

trace_bans = 'Ci'
for e in trace_bans:
    if e in ext_bans:
        logging.error('m_trace: "{}" conflicting with existing extban'.format(e))

@ircd.Modules.hooks.local_connect()
def connect_hook(self, localServer):
    if not hasattr(localServer, 'geodata'):
        localServer.geodata = {} ### Store info with IP.
    if self.ip not in localServer.geodata:
        url = 'https://extreme-ip-lookup.com/json/'+self.ip
        #url = 'http://ip-api.com/json/'+self.ip
        with urllib.request.urlopen(url) as response:
            json_res = json.load(response)
            localServer.geodata[self.ip] = json_res

@ircd.Modules.support(('EXTBAN='+prefix+','+trace_bans, True)) ### (support string, boolean if support must be sent to other servers)
@ircd.Modules.hooks.pre_local_chanmode()
@ircd.Modules.hooks.pre_remote_chanmode()
def extbans(self, localServer, channel, modes, params, modebuf, parambuf):
    try:
        paramcount = 0
        for m in modes:
            if m in '-+':
                action = m
                continue
            if m not in localServer.parammodes:
                continue
            if m not in 'beI':
                paramcount += 1
                continue

            param = params[paramcount]
            r_string = ''
            for r in trace_bans:
                r_string += '{}{}|'.format(prefix, r)
            r_string = r_string[:-1]
            traceban_check = re.findall("^("+r_string+"):(.*)", param)
            if not traceban_check or not traceban_check[0][1]:
                paramcount += 1
                #logging.info('Param {} is invalid for {}{}'.format(param, action, m))
                continue

            logging.info('Param for {}{} set: {}'.format(action, m, param))

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
                if action == '+' and param not in c:
                    modebuf.append(m)
                    parambuf.append(param)
                    c[param] = {}
                    c[param]['setter'] = setter
                    c[param]['ctime'] = int(time.time())

    except Exception as ex:
        logging.exception(ex)

@ircd.Modules.hooks.pre_local_join()
def join(self, localServer, channel):
    try:
        overrides = []
        invite_override = False
        if self in channel.invites:
            invite_override = channel.invites[self]['override']
        if invite_override:
            overrides.append('b')
            overrides.append('i')

        if hasattr(localServer, 'geodata') and self.ip in localServer.geodata:
            ### Exceptions.
            if 'b' not in overrides:
                for e in [e for e in channel.excepts if e.startswith('~C')]: ### Country except.
                    country = e.split(':')[1]
                    if match(country.lower(), localServer.geodata[self.ip]['country'].lower()) or match(country.lower(), localServer.geodata[self.ip]['countryCode'].lower()):
                        overrides.append('b')
                for e in [e for e in channel.excepts if e.startswith('~i')]: ### ISP except.
                    exceptIsp = e.split(':')[1]
                    if localServer.geodata[self.ip]['isp'].lower() == exceptIsp.lower() or invite_override and 'b' not in overrides:
                        overrides.append('b')

            for b in [b for b in channel.bans if b.startswith('~i')]: ### ISP ban.
                isp = b.split(':')[1]
                if match(isp.lower(), localServer.geodata[self.ip]['isp'].lower()) and not checkMatch(self, localServer, 'e', channel) and 'b' not in overrides:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, None, overrides)

            for b in [b for b in channel.bans if b.startswith('~C')]: ### Country ban.
                country = b.split(':')[1]
                if (match(country.lower(), localServer.geodata[self.ip]['country'].lower()) or match(country.lower(), localServer.geodata[self.ip]['countryCode'].lower())) and not checkMatch(self, localServer, 'e', channel) and 'b' not in overrides:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, None, overrides)
            for b in [b for b in channel.bans if b.startswith('~i')]: ### ISP ban.
                isp = b.split(':')[1]
                if match(isp.lower(), localServer.geodata[self.ip]['isp'].lower()) and not checkMatch(self, localServer, 'e', channel) and 'b' not in overrides:
                    self.sendraw(474, '{} :Cannot join channel (+b)'.format(channel.name))
                    return (False, None, overrides)

            for i in channel.invex:
                if i.startswith('~C'):
                    country = i.split(':')[1].lower()
                    if 'i' in channel.modes and match(country, localServer.geodata[self.ip]['country'].lower()) or match(country, localServer.geodata[self.ip]['countryCode'].lower()):
                        overrides.append('i')
                if i.startswith('~i'):
                    isp = i.split(':')[1].lower()
                    if 'i' in channel.modes and match(isp, localServer.geodata[self.ip]['isp'].lower()) and 'i' not in overrides:
                        overrides.append('i')

        return (True, None, overrides)

    except Exception as ex:
        logging.exception(ex)
